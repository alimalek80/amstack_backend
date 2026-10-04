from django.urls import path

from . import views

urlpatterns = [
    path("health/", views.health, name="health"),
    path("settings/", views.SiteSettingsView.as_view(), name="site-settings"),
]
