from django.db import models


class Technology(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "technologies"

    def __str__(self):
        return self.name


class Service(models.Model):
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    summary = models.CharField(max_length=300)
    icon = models.ImageField(
        upload_to="services/icons/",
        blank=True,
        help_text="Small symbol shown at the top left of the service card (square works best).",
    )
    description = models.TextField(
        blank=True,
        help_text="Write [image 1], [image 2]... on their own line to place the images "
        "added below at that spot. Images not mentioned appear after the text.",
    )
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class ServiceImage(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="services/images/")
    alt = models.CharField(max_length=200, blank=True, help_text="Short description for accessibility.")
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(
        default=0, help_text="Image 1 is the lowest number, image 2 the next, and so on."
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.service.title} image {self.pk}"


class Project(models.Model):
    title = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    client_name = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=300)
    problem = models.TextField(blank=True)
    solution = models.TextField(blank=True)
    result = models.TextField(blank=True)
    tech_stack = models.ManyToManyField(Technology, blank=True, related_name="projects")
    cover_image = models.ImageField(upload_to="projects/", blank=True)
    live_url = models.URLField(blank=True)
    repo_url = models.URLField(blank=True, help_text="GitHub repository link (optional).")
    order = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "-id"]

    def __str__(self):
        return self.title


class ProjectImage(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="projects/gallery/")
    alt = models.CharField(max_length=200, blank=True, help_text="Short description for accessibility.")
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(
        default=0, help_text="Lowest number is shown first in the project gallery."
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.project.title} image {self.pk}"
