from django.test import TestCase

from .models import SiteSettings


class CoreApiTests(TestCase):
    def test_health(self):
        self.assertEqual(self.client.get("/api/health/").json(), {"status": "ok"})

    def test_settings_returns_defaults_and_keeps_a_single_record(self):
        response = self.client.get("/api/settings/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("hero_headline", response.json())
        self.assertIn("about_photo", response.json())
        self.client.get("/api/settings/")
        self.assertEqual(SiteSettings.objects.count(), 1)
