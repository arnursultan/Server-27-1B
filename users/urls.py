from django.urls import path
from .views import RegisterView, UserListView, UserProfileView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('', UserListView.as_view(), name='user-list'),
    path('me/', UserProfileView.as_view(), name='user-profile'),
]