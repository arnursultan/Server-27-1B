import os
import time
import uuid
import redis

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.mail import send_mail

from users.models import Post

User = get_user_model()

def _redis_client():
    redis_url = getattr(settings, "REDIS_URL", None) or os.getenv(
        "REDIS_URL", "redis://127.0.0.1:6379/0"
    )
    return redis.Redis.from_url(redis_url, decode_responses=True)

def _user_display(user):
    name = getattr(user, "get_full_name", lambda: "")() or getattr(user, "first_name", "") or ""
    return name or getattr(user, "email", "") or f"user-{user.id}"

@require_GET
def ping_redis(request):
    r = _redis_client()
    return JsonResponse({"redis": "ok" if r.ping() else "down"})

@require_GET
def cached_posts_count(request):
    cache_key = "posts_count_demo"
    value = cache.get(cache_key)
    if value is None:
        time.sleep(2)
        value = Post.objects.count()
        cache.set(cache_key, value, timeout=30)
        src = "db"
    else:
        src = "cache"
    return JsonResponse({"posts_count": value, "source": src})

@require_GET
def hit_counter(request):
    r = _redis_client()
    user_part = request.user.id if request.user.is_authenticated else "anon"
    key = f"hitrate:{user_part}"
    hits = r.incr(key)
    r.expire(key, 3600)
    return JsonResponse({"hits": hits, "ttl_sec": r.ttl(key)})

@require_GET
def send_email_verification(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_active:
        return JsonResponse({"status": "already active"})

    if not getattr(user, "email", None):
        return JsonResponse({"status": "user has no email"}, status=400)

    r = _redis_client()
    token = str(uuid.uuid4())
    key = f"email_verify:{token}"
    r.set(key, user,id, ex=600)

    base = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    link = f"{base}/api/redis/verify-email/{token}/"

    send_mail(
        subject="Verify your account",
        message=f"Hello {_user_display(user) }, please verify your account: {link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,

    return JsonResponse({"status": "email sent", "ttl_sec": r.ttl(key)})
