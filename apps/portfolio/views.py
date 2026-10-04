from rest_framework import generics

from .models import Project, Service
from .serializers import (
    ProjectDetailSerializer,
    ProjectListSerializer,
    ServiceDetailSerializer,
    ServiceListSerializer,
)


class ServiceListView(generics.ListAPIView):
    serializer_class = ServiceListSerializer
    queryset = Service.objects.filter(is_published=True)


class ServiceDetailView(generics.RetrieveAPIView):
    serializer_class = ServiceDetailSerializer
    queryset = Service.objects.filter(is_published=True).prefetch_related("images")
    lookup_field = "slug"


class ProjectListView(generics.ListAPIView):
    serializer_class = ProjectListSerializer

    def get_queryset(self):
        queryset = Project.objects.filter(is_published=True).prefetch_related("tech_stack")
        if self.request.query_params.get("featured", "").lower() in {"1", "true"}:
            queryset = queryset.filter(is_featured=True)
        return queryset


class ProjectDetailView(generics.RetrieveAPIView):
    serializer_class = ProjectDetailSerializer
    queryset = Project.objects.filter(is_published=True).prefetch_related("tech_stack")
    lookup_field = "slug"
