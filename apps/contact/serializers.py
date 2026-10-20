from rest_framework import serializers

from apps.portfolio.models import Project, Service

from .models import ContactMessage

TOPIC_ERRORS = {
    "does_not_exist": "This option is not available. Please choose another one.",
    "invalid": "This option is not available. Please choose another one.",
}


class ContactMessageSerializer(serializers.ModelSerializer):
    # Honeypot: hidden from real visitors, bots tend to fill every field.
    website = serializers.CharField(required=False, allow_blank=True, write_only=True)
    # Optional topic, sent as the slug of a published service or project.
    service = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Service.objects.filter(is_published=True),
        required=False,
        allow_null=True,
        error_messages=TOPIC_ERRORS,
    )
    project = serializers.SlugRelatedField(
        slug_field="slug",
        queryset=Project.objects.filter(is_published=True),
        required=False,
        allow_null=True,
        error_messages=TOPIC_ERRORS,
    )

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message", "budget", "service", "project", "website"]
        extra_kwargs = {"message": {"max_length": 5000}}

    def validate(self, attrs):
        if attrs.get("service") and attrs.get("project"):
            raise serializers.ValidationError("Choose either a service or a project, not both.")
        return attrs


# ----- Dashboard API (superusers only) -----


class DashboardContactMessageSerializer(serializers.ModelSerializer):
    budget_label = serializers.SerializerMethodField()
    topic = serializers.SerializerMethodField()

    class Meta:
        model = ContactMessage
        fields = ["id", "name", "email", "message", "budget", "budget_label", "created_at", "is_read", "topic"]
        # Only is_read can be written. Unknown or read-only keys in a PATCH are ignored.
        read_only_fields = ["id", "name", "email", "message", "budget", "created_at"]

    def get_budget_label(self, obj):
        return obj.get_budget_display() or None

    def get_topic(self, obj):
        topic = obj.topic
        if topic is None:
            return None
        kind, item = topic
        return {"type": kind, "title": item.title, "slug": item.slug, "is_published": item.is_published}

    def validate(self, attrs):
        if "is_read" not in attrs:
            raise serializers.ValidationError({"is_read": ["This field is required."]})
        return attrs
