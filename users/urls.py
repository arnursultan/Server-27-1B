from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RegisterView, UserListView, UserProfileView,
    PostViewSet, ProtectedTestView, LogoutView,
    ChangePasswordView, CustomTokenObtainPairView
)
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('users/', UserListView.as_view(), name='user-list'),
    path('profile/', UserProfileView.as_view(), name='user-profile'),

    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('logout/', LogoutView.as_view(), name='logout'),

    path('protected/', ProtectedTestView.as_view(), name='protected'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

    path('', include(router.urls)),
]
