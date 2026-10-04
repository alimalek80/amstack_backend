from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APITestCase

from .models import ContactMessage
from .notifications import _send_email

PAYLOAD = {
    "name": "Jan",
    "email": "jan@example.com",
    "message": "Hello, I need a Django backend.",
    "budget": "2k_5k",
}


class ContactApiTests(APITestCase):
    url = "/api/contact/"

    def setUp(self):
        cache.clear()

    @mock.patch("apps.contact.views.notify_new_message")
    def test_valid_message_is_saved_and_owner_notified(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, PAYLOAD, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 1)
        notify.assert_called_once()

    @mock.patch("apps.contact.views.notify_new_message")
    def test_honeypot_is_dropped_silently(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.url, {**PAYLOAD, "website": "http://spam.example"}, format="json"
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 0)
        notify.assert_not_called()

    def test_invalid_email_is_rejected(self):
        response = self.client.post(self.url, {**PAYLOAD, "email": "nope"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_budget_is_optional(self):
        payload = {key: value for key, value in PAYLOAD.items() if key != "budget"}
        self.assertEqual(self.client.post(self.url, payload, format="json").status_code, 201)

    def test_sixth_message_within_an_hour_is_throttled(self):
        for _ in range(5):
            self.assertEqual(self.client.post(self.url, PAYLOAD, format="json").status_code, 201)
        self.assertEqual(self.client.post(self.url, PAYLOAD, format="json").status_code, 429)


class NotificationTests(TestCase):
    @override_settings(CONTACT_NOTIFY_EMAIL="me@example.com")
    def test_email_uses_reply_to_and_has_a_safe_subject(self):
        message = ContactMessage(
            name="Jan\nBcc: x@evil.com", email="jan@example.com", message="Hi", budget=""
        )
        _send_email(message)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].reply_to, ["jan@example.com"])
