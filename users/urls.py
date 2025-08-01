from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PostViewSet, RegisterView, UserListView, UserProfileView

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='post')

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('', UserListView.as_view(), name='user-list'),
    path('me/', UserProfileView.as_view(), name='user-profile'),
    path('', include(router.urls)),
]
