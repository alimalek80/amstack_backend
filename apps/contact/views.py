from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .notifications import notify_new_message
from .serializers import ContactMessageSerializer


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
