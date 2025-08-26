from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from users.views import login_page, home_view, logout_view, force_logout_before_login

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('auth/', include('social_django.urls', namespace='social')),

    path('auth/force-login/<str:provider>/', force_logout_before_login, name='force-login'),

    path('login-page/', login_page, name='login-page'),
    path('', home_view, name='home'),
    path('logout/', logout_view, name='logout'),
    path("api/redis/", include("redisapp.urls")),

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
