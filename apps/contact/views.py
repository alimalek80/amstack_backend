from django.db import transaction
from django.db.models import F
from rest_framework import generics, mixins, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.blog.views import DashboardMixin

from .models import ContactMessage
from .notifications import notify_new_message
from .serializers import ContactMessageSerializer, DashboardContactMessageSerializer


class ContactCreateView(generics.CreateAPIView):
    serializer_class = ContactMessageSerializer
    permission_classes = [AllowAny]
    # No authentication: a logged-in admin testing the form must not hit CSRF checks.
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        honeypot = serializer.validated_data.pop("website", "")
        if not honeypot:
            message = serializer.save()
            transaction.on_commit(lambda: notify_new_message(message))
        # Bots get the same success answer, so they cannot tell they were dropped.
        return Response(
            {"detail": "Thanks! Your message has been sent."},
            status=status.HTTP_201_CREATED,
        )


# ----- Dashboard API (superusers only) -----


class DashboardContactMessageViewSet(
    DashboardMixin, mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet
):
    """Contact requests for the dashboard: list all, and toggle is_read. No create or delete."""

    serializer_class = DashboardContactMessageSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        # Group order: services (site order), then projects (site order), then no topic;
        # newest first inside each group. The frontend groups by first appearance.
        return ContactMessage.objects.select_related("service", "project").order_by(
            F("service__order").asc(nulls_last=True),
            F("service__title").asc(nulls_last=True),
            F("service__id").asc(nulls_last=True),
            F("project__order").asc(nulls_last=True),
            F("project__id").desc(nulls_last=True),
            "-created_at",
            "-id",
        )
