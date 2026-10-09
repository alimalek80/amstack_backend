from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from .content import empty_doc, plain_text


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class BlogImage(models.Model):
    """An uploaded image used as a post cover or inside a post body."""

    image = models.ImageField(upload_to="blog/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.image.name


class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    excerpt = models.TextField(blank=True, help_text="Short summary shown in the post list.")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts"
    )
    cover = models.ForeignKey(
        BlogImage, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    # Rich text document from the dashboard editor (Tiptap JSON); see content.py.
    body = models.JSONField(default=empty_doc, blank=True)
    repo_url = models.URLField(blank=True, help_text="GitHub repository link (optional).")
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        if self.is_published and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def _unique_slug(self):
        base = slugify(self.title)[:200] or "post"
        slug, n = base, 2
        while Post.objects.filter(slug=slug).exclude(pk=self.pk).exists():
            slug, n = f"{base}-{n}", n + 1
        return slug

    @property
    def reading_minutes(self):
        return max(1, round(len(plain_text(self.body).split()) / 200))
