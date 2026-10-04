from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "budget", "created_at", "is_read")
    list_filter = ("is_read", "budget")
    search_fields = ("name", "email", "message")
    readonly_fields = ("name", "email", "message", "budget", "created_at")

    def has_add_permission(self, request):
        # Messages come only from the public form.
        return False
