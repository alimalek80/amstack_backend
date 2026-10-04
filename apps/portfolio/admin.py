from django.contrib import admin

from .models import Project, Service, Technology


@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "is_published")
    list_editable = ("order", "is_published")
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "client_name", "order", "is_featured", "is_published")
    list_editable = ("order", "is_featured", "is_published")
    list_filter = ("is_published", "is_featured")
    search_fields = ("title", "client_name", "summary")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("tech_stack",)
