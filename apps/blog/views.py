from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db.models import Count, F
from django.http import Http404
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


# Lower-cased substrings that mark crawlers, previews and audit tools. An empty UA counts as a bot.
BOT_UA_MARKERS = ("bot", "crawler", "spider", "slurp", "headless", "lighthouse")


def is_bot(user_agent: str) -> bool:
    ua = user_agent.lower()
    return not ua or any(marker in ua for marker in BOT_UA_MARKERS)


def is_cross_site(request) -> bool:
    """True when the browser says the POST came from another site.

    The endpoint has no CSRF check and a bodiless POST needs no CORS preflight, so any
    third-party page could otherwise add a view for each of its visitors. Requests that
    send neither header (old browsers, curl) are not cross-site by this test; the per-IP
    throttle covers them.
    """
    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site is not None and fetch_site != "same-origin":
        return True
    origin = request.headers.get("Origin")
    return origin is not None and origin not in settings.CSRF_TRUSTED_ORIGINS


class PostViewCountView(APIView):
    """Records one view of a published post and returns the new total."""

    permission_classes = [AllowAny]
    # No authentication: no CSRF check, and a logged-in admin counts like anyone else.
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "blog_view"

    def post(self, request, slug):
        posts = Post.objects.filter(slug=slug, is_published=True)
        if not is_bot(request.META.get("HTTP_USER_AGENT", "")) and not is_cross_site(request):
            # One atomic UPDATE ... SET view_count = view_count + 1. QuerySet.update()
            # skips save(), so auto_now on updated_at is not triggered.
            posts.update(view_count=F("view_count") + 1)
        view_count = posts.values_list("view_count", flat=True).first()
        if view_count is None:
            raise Http404
        return Response({"view_count": view_count})


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
