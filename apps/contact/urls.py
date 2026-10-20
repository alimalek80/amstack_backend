from django.urls import include, path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("contact-messages", views.DashboardContactMessageViewSet, basename="dashboard-contact-message")

urlpatterns = [
    path("contact/", views.ContactCreateView.as_view(), name="contact-create"),
    path("dashboard/", include(router.urls)),
]
