from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("posts", views.DashboardPostViewSet, basename="dashboard-post")
router.register("categories", views.DashboardCategoryViewSet, basename="dashboard-category")

urlpatterns = [
    path("blog/categories/", views.CategoryListView.as_view(), name="blog-category-list"),
    path("blog/posts/", views.PostListView.as_view(), name="blog-post-list"),
    path("blog/posts/<slug:slug>/", views.PostDetailView.as_view(), name="blog-post-detail"),
    path("dashboard/auth/me/", views.MeView.as_view(), name="dashboard-me"),
    path("dashboard/auth/login/", views.LoginView.as_view(), name="dashboard-login"),
    path("dashboard/auth/logout/", views.LogoutView.as_view(), name="dashboard-logout"),
    path("dashboard/images/", views.DashboardImageUploadView.as_view(), name="dashboard-image"),
    path("dashboard/", include(router.urls)),
]
