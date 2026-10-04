from rest_framework import serializers

from .models import Project, Service, ServiceImage, Technology


class TechnologySerializer(serializers.ModelSerializer):
    class Meta:
        model = Technology
        fields = ["name", "slug"]


class ServiceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServiceImage
        fields = ["image", "alt", "caption"]


class ServiceListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ["slug", "title", "summary", "icon"]


class ServiceDetailSerializer(serializers.ModelSerializer):
    images = ServiceImageSerializer(many=True, read_only=True)

    class Meta:
        model = Service
        fields = ["slug", "title", "summary", "icon", "description", "images"]


class ProjectListSerializer(serializers.ModelSerializer):
    tech_stack = TechnologySerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = [
            "slug",
            "title",
            "client_name",
            "summary",
            "cover_image",
            "live_url",
            "is_featured",
            "tech_stack",
        ]


class ProjectDetailSerializer(ProjectListSerializer):
    class Meta(ProjectListSerializer.Meta):
        fields = ProjectListSerializer.Meta.fields + ["problem", "solution", "result"]
