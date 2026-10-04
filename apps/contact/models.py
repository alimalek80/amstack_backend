from django.db import models


class ContactMessage(models.Model):
    BUDGET_CHOICES = [
        ("under_2k", "Under €2,000"),
        ("2k_5k", "€2,000 – €5,000"),
        ("5k_10k", "€5,000 – €10,000"),
        ("over_10k", "Over €10,000"),
        ("not_sure", "Not sure yet"),
    ]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    message = models.TextField()
    budget = models.CharField(max_length=20, choices=BUDGET_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}>"
