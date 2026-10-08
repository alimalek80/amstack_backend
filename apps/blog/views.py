from django.contrib.auth import authenticate, login, logout
from django.db.models import Count
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import generics, status, viewsets
from rest_framework.authentication import SessionAuthentication
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import BlogImage, Category, Post
from .serializers import (
    CategorySerializer,
    DashboardCategorySerializer,
    DashboardImageSerializer,
    DashboardPostListSerializer,
    DashboardPostSerializer,
    PostDetailSerializer,
    PostListSerializer,
)

# ----- Public API -----


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer

    def get_queryset(self):
        return CategorySerializer.public_queryset()


class PostListView(generics.ListAPIView):
    serializer_class = PostListSerializer

    def get_queryset(self):
        queryset = Post.objects.filter(is_published=True).select_related("category", "cover")
        category = self.request.query_params.get("category")
        if category:
            queryset = queryset.filter(category__slug=category)
        return queryset


class PostDetailView(generics.RetrieveAPIView):
    serializer_class = PostDetailSerializer
    queryset = Post.objects.filter(is_published=True).select_related("category", "cover")
    lookup_field = "slug"


# ----- Dashboard API (superusers only, session login from the Next.js dashboard) -----


class IsSuperuser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_superuser)


def _user_data(user):
    return {"email": user.email, "name": user.get_full_name()}


class DashboardMixin:
    # SessionAuthentication also enforces CSRF on every unsafe request.
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsSuperuser]


@method_decorator(ensure_csrf_cookie, name="dispatch")
class MeView(APIView):
    """Who is logged in. Also sets the CSRF cookie the dashboard sends back."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        user = request.user
        if user.is_authenticated and user.is_superuser:
            return Response(_user_data(user))
        return Response({"detail": "Not logged in."}, status=status.HTTP_401_UNAUTHORIZED)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "dashboard_login"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        password = str(request.data.get("password", ""))
        user = authenticate(request, email=email, password=password)
        if user is None or not user.is_superuser:
            return Response(
                {"detail": "Email or password is incorrect."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(_user_data(user))


class LogoutView(DashboardMixin, APIView):
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardPostViewSet(DashboardMixin, viewsets.ModelViewSet):
    queryset = Post.objects.select_related("category", "cover").order_by("-updated_at")

    def get_serializer_class(self):
        return DashboardPostListSerializer if self.action == "list" else DashboardPostSerializer


class DashboardCategoryViewSet(DashboardMixin, viewsets.ModelViewSet):
    serializer_class = DashboardCategorySerializer
    queryset = Category.objects.annotate(post_count=Count("posts"))


class DashboardImageUploadView(DashboardMixin, generics.CreateAPIView):
    serializer_class = DashboardImageSerializer
    parser_classes = [MultiPartParser, FormParser]
    queryset = BlogImage.objects.all()
