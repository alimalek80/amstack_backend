from django.db import models


class SiteSettings(models.Model):
    """Single-record model holding the editable texts and links of the site."""

    hero_headline = models.CharField(
        max_length=200, default="Websites, online stores, bots and SaaS, built end to end"
    )
    hero_subheadline = models.CharField(
        max_length=300,
        blank=True,
        default=(
            "Company sites, shops, custom features, website chatbots, "
            "Telegram bots and SaaS platforms, from simple to advanced."
        ),
    )
    about_text = models.TextField(blank=True)
    about_photo = models.ImageField(upload_to="about/", blank=True)
    email = models.EmailField(blank=True)
    linkedin_url = models.URLField(blank=True)
    github_url = models.URLField(blank=True)
    booking_url = models.URLField(blank=True)

    class Meta:
        verbose_name = "site settings"
        verbose_name_plural = "site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Site settings"
