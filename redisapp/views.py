from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
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

from users.models import Post
from redisapp.tasks import send_email_task

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
@extend_schema(summary='Проверка соединения с Redis')
@extend_schema(summary='Ping Redis')
def ping_redis(request):
    r = _redis_client()
    return JsonResponse({"redis": "ok" if r.ping() else "down"})

@require_GET
@extend_schema(summary='Кэшированный подсчёт постов')
@extend_schema(summary='Кэш: количество постов')
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
@extend_schema(summary='Счётчик запросов пользователя')
@extend_schema(summary='Счётчик хитов')
def hit_counter(request):
    r = _redis_client()
    user_part = request.user.id if request.user.is_authenticated else "anon"
    key = f"hitrate:{user_part}"
    hits = r.incr(key)
    r.expire(key, 3600)
    return JsonResponse({"hits": hits, "ttl_sec": r.ttl(key)})

@require_GET
@extend_schema(summary='Очистка всего кэша')
@extend_schema(summary='Очистка кэша')
def clear_cache(request):
    cache.clear()
    return JsonResponse({"cleared": True})

@require_GET
@extend_schema(summary='Отправка письма для подтверждения email')
@extend_schema(summary='Отправка письма подтверждения')
def send_email_verification(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_active:
        return JsonResponse({"status": "already active"})

    if not getattr(user, "email", None):
        return JsonResponse({"status": "user has no email"}, status=400)

    r = _redis_client()
    token = str(uuid.uuid4())
    key = f"email_verify:{token}"
    r.set(key, user.id, ex=600)

    base = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    link = f"{base}/api/redis/verify-email/{token}/"

    async_result = send_email_task.apply_async(
        kwargs=dict(
            subject="Verify your account",
            to=[user.email],
            from_email=None,
            body=f"Hello { _user_display(user) }, please verify your account: {link}",
        ),
        queue="emails",
        countdown=0,
        expires=60 * 60,
    )

    return JsonResponse({
        "status": "email queued",
        "ttl_sec": r.ttl(key),
        "task_id": async_result.id,
    })

@require_GET
@extend_schema(summary='Подтверждение email')
def verify_email(request, token):
    r = _redis_client()
    key = f"email_verify:{token}"
    user_id = r.get(key)
    if not user_id:
        return JsonResponse({"status": "invalid or expired"}, status=400)

    user = get_object_or_404(User, id=user_id)
    user.is_active = True
    user.save()

    r.delete(key)
    return JsonResponse({"status": "email verified"})

@require_GET
@extend_schema(summary='Запрос сброса пароля')
def request_password_reset(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if not getattr(user, "email", None):
        return JsonResponse({"status": "user has no email"}, status=400)

    r = _redis_client()
    token = str(uuid.uuid4())
    key = f"pwd_reset:{token}"
    r.set(key, user.id, ex=300)

    base = getattr(settings, "PUBLIC_BASE_URL", "http://127.0.0.1:8000")
    link = f"{base}/api/redis/reset-password/{token}/?new_pwd=NewStrongPass195"

    async_result = send_email_task.apply_async(
        kwargs=dict(
            subject="Password reset request",
            to=[user.email],
            from_email=None,
            body=f"Hello { _user_display(user) }, click here to reset your password: {link}",
        ),
        queue="emails",
        countdown=0,
        expires=30 * 60,
    )

    return JsonResponse({
        "status": "email queued",
        "ttl_sec": r.ttl(key),
        "task_id": async_result.id,
    })

@require_GET
@extend_schema(summary='Сброс пароля')
def reset_password(request, token):
    new_pwd = request.GET.get("new_pwd")
    if not new_pwd:
        return JsonResponse({"status": "missing new_pwd"}, status=400)

    r = _redis_client()
    key = f"pwd_reset:{token}"
    user_id = r.get(key)
    if not user_id:
        return JsonResponse({"status": "invalid or expired"}, status=400)

    user = get_object_or_404(User, id=user_id)
    user.set_password(new_pwd)
    user.save()

    r.delete(key)
    return JsonResponse({"status": "password changed"})

@require_GET
@extend_schema(summary='Просмотр поста (увеличивает счётчик)')
def post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    r = _redis_client()
    key = f"post_views:{post.id}"
    views = r.incr(key)
    r.expire(key, 86400)
    return JsonResponse({"post": post.id, "views": views, "ttl_sec": r.ttl(key)})
