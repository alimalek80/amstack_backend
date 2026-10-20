from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "topic_display", "budget", "created_at", "is_read")
    list_filter = (
        "is_read",
        "budget",
        ("service", admin.RelatedOnlyFieldListFilter),
        ("project", admin.RelatedOnlyFieldListFilter),
    )
    list_select_related = ("service", "project")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "message", "budget", "service", "project", "created_at")

    @admin.display(description="Topic")
    def topic_display(self, obj):
        topic = obj.topic
        if topic is None:
            return "-"
        kind, item = topic
        return f"{kind.title()}: {item.title}"

    def has_add_permission(self, request):
        # Messages come only from the public form.
        return False
