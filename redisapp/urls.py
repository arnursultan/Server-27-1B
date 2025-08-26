from django.urls import path
from .views import (
    ping_redis, cached_posts_count, hit_counter,
    clear_cache, send_email_verification, verify_email,
    request_password_reset, reset_password, post_view
)

urlpatterns = [
    path('ping/', ping_redis),
    path('cached-posts-count/', cached_posts_count),
    path('hits/', hit_counter),
    path('clear-cache/', clear_cache),

    path('send-email-verification/<int:user_id>/', send_email_verification),
    path('verify-email/<uuid:token>/', verify_email),

    path('request-password-reset/<int:user_id>/', request_password_reset),
    path('reset-password/<uuid:token>/', reset_password),

    path('post-view/<int:post_id>/', post_view),
]