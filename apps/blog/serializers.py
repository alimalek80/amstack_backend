from django.db.models import Count, Q
from django.utils.text import slugify
from rest_framework import serializers

from .content import clean_doc
from .models import BlogImage, Category, Post

# ----- Public API -----

class CategorySerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["name", "slug", "description", "post_count"]

    @staticmethod
    def public_queryset():
        published = Count("posts", filter=Q(posts__is_published=True))
        return Category.objects.annotate(post_count=published).filter(post_count__gt=0)


class CategoryRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["name", "slug"]


class PostListSerializer(serializers.ModelSerializer):
    category = CategoryRefSerializer(read_only=True)
    cover_image = serializers.SerializerMethodField()
    reading_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = [
            "title",
            "slug",
            "excerpt",
            "category",
            "cover_image",
            "published_at",
            "reading_minutes",
        ]

    def get_cover_image(self, obj):
        return obj.cover.image.url if obj.cover else None


class PostDetailSerializer(PostListSerializer):
    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ["body", "repo_url", "updated_at"]


# ----- Dashboard API (superusers only) -----

class DashboardCategorySerializer(serializers.ModelSerializer):
    post_count = serializers.IntegerField(read_only=True)
    slug = serializers.SlugField(max_length=120, required=False, allow_blank=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "order", "post_count"]

    def validate(self, attrs):
        if "slug" in attrs or self.instance is None:
            name = attrs.get("name") or getattr(self.instance, "name", "")
            attrs["slug"] = attrs.get("slug") or slugify(name)[:120]
            if not attrs["slug"]:
                raise serializers.ValidationError({"slug": "Enter a slug."})
            taken = Category.objects.filter(slug=attrs["slug"])
            if self.instance is not None:
                taken = taken.exclude(pk=self.instance.pk)
            if taken.exists():
                raise serializers.ValidationError({"slug": "A category with this slug already exists."})
        return attrs


class DashboardImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = BlogImage
        fields = ["id", "image", "url"]
        extra_kwargs = {"image": {"write_only": True}}

    def get_url(self, obj):
        return obj.image.url

    def validate_image(self, image):
        if image.size > 8 * 1024 * 1024:
            raise serializers.ValidationError("Images must be 8 MB or smaller.")
        return image


class DashboardPostListSerializer(serializers.ModelSerializer):
    category = CategoryRefSerializer(read_only=True)

    class Meta:
        model = Post
        fields = ["id", "title", "slug", "category", "is_published", "published_at", "updated_at"]


class DashboardPostSerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=220, required=False, allow_blank=True)
    cover_url = serializers.SerializerMethodField()
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    reading_minutes = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "category",
            "category_name",
            "cover",
            "cover_url",
            "body",
            "repo_url",
            "is_published",
            "published_at",
            "reading_minutes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["published_at", "created_at", "updated_at"]

    def get_cover_url(self, obj):
        return obj.cover.image.url if obj.cover else None

    def validate_body(self, value):
        return clean_doc(value)

    def validate_slug(self, value):
        if value and Post.objects.filter(slug=value).exclude(pk=getattr(self.instance, "pk", None)).exists():
            raise serializers.ValidationError("Another post already uses this slug.")
        return value
