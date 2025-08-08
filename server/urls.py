from django.contrib import admin
from django.urls import path, include
from users.views import login_page, home_view, logout_view, force_logout_before_login

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('auth/', include('social_django.urls', namespace='social')),

    path('auth/force-login/<str:provider>/', force_logout_before_login, name='force-login'),

    path('login-page/', login_page, name='login-page'),
    path('', home_view, name='home'),
    path('logout/', logout_view, name='logout'),
]
