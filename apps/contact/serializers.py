from rest_framework import serializers

from .models import ContactMessage


class ContactMessageSerializer(serializers.ModelSerializer):
    # Honeypot: hidden from real visitors, bots tend to fill every field.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message", "budget", "website"]
        extra_kwargs = {"message": {"max_length": 5000}}
