from drf_spectacular.utils import (
    extend_schema,
    extend_schema_view,
    OpenApiParameter,
    OpenApiResponse,
)
from rest_framework import generics, permissions, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CustomUser, Post
from .serializers import (
    RegisterSerializer,
    UserSerializer,
    PostSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
)

from .permissions import IsOwnerOrReadOnly, IsAdmin, IsOwnerOrAdmin
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout

@extend_schema(summary='Регистрация нового пользователя')
@extend_schema(
    summary="Регистрация",
    request=RegisterSerializer,
    responses={201: UserSerializer}
)
class RegisterView(generics.CreateAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema(summary='Список пользователей (только для админа)')
@extend_schema(
    summary="Список пользователей (простая вью)",
    responses={200: UserSerializer(many=True)}
)
class UserListView(generics.ListAPIView):
    queryset = CustomUser.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]


@extend_schema(summary='Профиль текущего пользователя')
@extend_schema(
    summary="Профиль текущего пользователя",
    responses={200: UserSerializer}
)
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]

    def get_object(self):
        return self.request.user


@extend_schema(summary='CRUD операции с постами')
@extend_schema_view(
    list=extend_schema(summary="Список постов", responses={200: PostSerializer(many=True)}),
    retrieve=extend_schema(summary="Получить пост", responses={200: PostSerializer}),
    create=extend_schema(summary="Создать пост", responses={201: PostSerializer}),
    partial_update=extend_schema(summary="Частичное обновление поста", responses={200: PostSerializer}),
    update=extend_schema(summary="Обновить пост", responses={200: PostSerializer}),
    destroy=extend_schema(summary="Удалить пост", responses={204: OpenApiResponse(description='Удалено')})
)
class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


@extend_schema(summary='Получение JWT токена')
@extend_schema(summary="Получить JWT токены (login)")
class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@extend_schema(summary='Тест защищённого эндпоинта')
@extend_schema(summary="Пример защищённого эндпоинта")
class ProtectedTestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response({
            "message": "JWT работает! Вы авторизованы.",
            "user": request.user.email
        })


@extend_schema(summary='Выход и блэклист токена')
@extend_schema(summary="Выход (logout)")
class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"detail": "Вы вышли из системы."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(summary='Смена пароля пользователем')
@extend_schema(summary="Смена пароля")
class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        user = request.user

        if serializer.is_valid():
            if not user.check_password(serializer.validated_data['old_password']):
                return Response({"old_password": "Неверный старый пароль."}, status=status.HTTP_400_BAD_REQUEST)

            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"detail": "Пароль успешно изменён."}, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(exclude=True)
def login_page(request):
    print("Текущий пользователь:", request.user)
    return render(request, 'login.html')


@extend_schema(exclude=True)
def home_view(request):
    return render(request, 'home.html', {'user': request.user})


@extend_schema(exclude=True)
def logout_view(request):
    logout(request)
    return redirect('login-page')


@extend_schema(exclude=True)
def force_logout_before_login(request, provider):
    logout(request)
    return redirect(f'/auth/login/{provider}/')
