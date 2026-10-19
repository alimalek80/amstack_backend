from django.contrib import admin

from .models import BlogImage, Category, Post

# Posts are written in the Next.js dashboard (/admin-dashboard); these are a fallback.


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order")
    list_editable = ("order",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_published", "published_at", "updated_at", "view_count")
    list_filter = ("is_published", "category")
    search_fields = ("title", "excerpt")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("view_count",)


admin.site.register(BlogImage)
