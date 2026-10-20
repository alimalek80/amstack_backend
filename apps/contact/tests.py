import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.portfolio.models import Project, Service

from .models import ContactMessage
from .notifications import _send_email, _send_telegram, _summary

User = get_user_model()

PAYLOAD = {
    "name": "Test Person",
    "email": "test@example.com",
    "message": "Hello, I need a Django backend.",
    "budget": "2k_5k",
}

TOPIC_ERROR = "This option is not available. Please choose another one."


def create_topics(test):
    test.web_apps = Service.objects.create(title="Web apps", slug="web-apps", summary="x", is_published=True)
    test.draft_service = Service.objects.create(title="Draft service", slug="draft-service", summary="x")
    test.shop = Project.objects.create(title="Shop", slug="shop", summary="x", is_published=True)
    test.draft_project = Project.objects.create(title="Draft project", slug="draft-project", summary="x")


class ContactApiTests(APITestCase):
    url = "/api/contact/"

    def setUp(self):
        cache.clear()
        create_topics(self)

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

    @mock.patch("apps.contact.views.notify_new_message")
    def test_without_topic_saves_with_empty_fields(self, notify):
        for payload in (PAYLOAD, {**PAYLOAD, "service": "", "project": None}):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(self.url, payload, format="json")
            self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 2)
        for message in ContactMessage.objects.all():
            self.assertIsNone(message.service)
            self.assertIsNone(message.project)
        self.assertEqual(notify.call_count, 2)

    @mock.patch("apps.contact.views.notify_new_message")
    def test_valid_service_is_stored(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {**PAYLOAD, "service": "web-apps"}, format="json")
        self.assertEqual(response.status_code, 201)
        message = ContactMessage.objects.get()
        self.assertEqual(message.service, self.web_apps)
        self.assertIsNone(message.project)
        notify.assert_called_once()

    @mock.patch("apps.contact.views.notify_new_message")
    def test_valid_project_is_stored(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(self.url, {**PAYLOAD, "project": "shop"}, format="json")
        self.assertEqual(response.status_code, 201)
        message = ContactMessage.objects.get()
        self.assertEqual(message.project, self.shop)
        self.assertIsNone(message.service)
        notify.assert_called_once()

    def test_unknown_slug_is_rejected(self):
        response = self.client.post(self.url, {**PAYLOAD, "service": "nope"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"service": [TOPIC_ERROR]})
        response = self.client.post(self.url, {**PAYLOAD, "project": "nope"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"project": [TOPIC_ERROR]})
        # A non-string value gets the same message.
        response = self.client.post(self.url, {**PAYLOAD, "service": ["web-apps"]}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"service": [TOPIC_ERROR]})
        self.assertEqual(ContactMessage.objects.count(), 0)

    def test_unpublished_slug_is_rejected(self):
        response = self.client.post(self.url, {**PAYLOAD, "service": "draft-service"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"service": [TOPIC_ERROR]})
        response = self.client.post(self.url, {**PAYLOAD, "project": "draft-project"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"project": [TOPIC_ERROR]})
        self.assertEqual(ContactMessage.objects.count(), 0)

    @mock.patch("apps.contact.views.notify_new_message")
    def test_service_and_project_together_is_rejected(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.url, {**PAYLOAD, "service": "web-apps", "project": "shop"}, format="json"
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(), {"non_field_errors": ["Choose either a service or a project, not both."]}
        )
        self.assertEqual(ContactMessage.objects.count(), 0)
        notify.assert_not_called()

    @mock.patch("apps.contact.views.notify_new_message")
    def test_honeypot_with_topic_saves_nothing(self, notify):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                self.url,
                {**PAYLOAD, "service": "web-apps", "website": "http://spam.example"},
                format="json",
            )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(ContactMessage.objects.count(), 0)
        notify.assert_not_called()

    @mock.patch("apps.contact.views.notify_new_message")
    def test_success_body_is_unchanged_with_topic(self, notify):
        response = self.client.post(self.url, {**PAYLOAD, "project": "shop"}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"detail": "Thanks! Your message has been sent."})

    def test_sixth_message_within_an_hour_is_throttled(self):
        for _ in range(5):
            self.assertEqual(self.client.post(self.url, PAYLOAD, format="json").status_code, 201)
        self.assertEqual(self.client.post(self.url, PAYLOAD, format="json").status_code, 429)


class NotificationTests(TestCase):
    @override_settings(CONTACT_NOTIFY_EMAIL="me@example.com")
    def test_email_uses_reply_to_and_has_a_safe_subject(self):
        message = ContactMessage(
            name="Test\nBcc: x@evil.example", email="test@example.com", message="Hi", budget=""
        )
        _send_email(message)
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn("\n", mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].reply_to, ["test@example.com"])

    def test_summary_has_a_topic_line(self):
        create_topics(self)
        base = {"name": "Test Person", "email": "test@example.com", "message": "Hi"}
        self.assertIn("Topic: Service: Web apps\n", _summary(ContactMessage(service=self.web_apps, **base)))
        self.assertIn("Topic: Project: Shop\n", _summary(ContactMessage(project=self.shop, **base)))
        self.assertIn("Topic: -\n", _summary(ContactMessage(**base)))


class DashboardContactTests(TestCase):
    list_url = "/api/dashboard/contact-messages/"

    def setUp(self):
        create_topics(self)
        self.admin = User.objects.create_superuser(email="admin@example.com", password="pass-12345")
        User.objects.create_user(email="staff@example.com", password="pass-12345", is_staff=True)
        self.message = ContactMessage.objects.create(
            name="Test Person", email="test@example.com", message="Hi", service=self.web_apps
        )

    def detail_url(self, message):
        return f"{self.list_url}{message.pk}/"

    def patch(self, data, client=None, **extra):
        return (client or self.client).patch(
            self.detail_url(self.message), data, content_type="application/json", **extra
        )

    def test_closed_to_anonymous_and_staff(self):
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.patch({"is_read": True}).status_code, 403)
        self.client.login(email="staff@example.com", password="pass-12345")
        self.assertEqual(self.client.get(self.list_url).status_code, 403)
        self.assertEqual(self.patch({"is_read": True}).status_code, 403)
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_read)

    def test_superuser_list_shape_and_order(self):
        self.message.delete()
        service_a = Service.objects.create(
            title="Service A", slug="service-a", summary="x", order=1, is_published=True
        )
        service_b = Service.objects.create(
            title="Service B", slug="service-b", summary="x", order=0, is_published=True
        )
        service_u = Service.objects.create(
            title="Service U", slug="service-u", summary="x", order=2, is_published=True
        )
        project_p = Project.objects.create(title="Project P", slug="project-p", summary="x", is_published=True)

        def create(label, **fields):
            return ContactMessage.objects.create(
                name=f"Test {label}", email="test@example.com", message="Line one\nLine two", **fields
            )

        a = create("A", service=service_a, budget="2k_5k")
        b = create("B", service=service_b)
        u = create("U", service=service_u)
        p = create("P", project=project_p)
        # The newer message gets the lower id, so the order must come from created_at.
        none_new = create("None new")
        none_old = create("None old")
        now = timezone.now()
        ContactMessage.objects.filter(pk=none_new.pk).update(created_at=now - timedelta(hours=1))
        ContactMessage.objects.filter(pk=none_old.pk).update(created_at=now - timedelta(days=2))
        service_u.is_published = False
        service_u.save()

        self.client.force_login(self.admin)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, 200)
        rows = response.json()
        self.assertEqual(
            [row["id"] for row in rows], [b.pk, a.pk, u.pk, p.pk, none_new.pk, none_old.pk]
        )

        row_a = rows[1]
        self.assertEqual(
            set(row_a),
            {"id", "name", "email", "message", "budget", "budget_label", "created_at", "is_read", "topic"},
        )
        self.assertEqual(row_a["budget"], "2k_5k")
        self.assertEqual(row_a["budget_label"], "€2,000 – €5,000")
        self.assertEqual(row_a["message"], "Line one\nLine two")
        self.assertFalse(row_a["is_read"])
        self.assertEqual(
            row_a["topic"],
            {"type": "service", "title": "Service A", "slug": "service-a", "is_published": True},
        )
        self.assertEqual(
            rows[2]["topic"],
            {"type": "service", "title": "Service U", "slug": "service-u", "is_published": False},
        )
        self.assertEqual(
            rows[3]["topic"],
            {"type": "project", "title": "Project P", "slug": "project-p", "is_published": True},
        )
        self.assertIsNone(rows[4]["topic"])
        self.assertEqual(rows[4]["budget"], "")
        self.assertIsNone(rows[4]["budget_label"])

        # A deleted topic falls back to "no topic".
        service_a.delete()
        rows = self.client.get(self.list_url).json()
        self.assertIsNone(next(row for row in rows if row["id"] == a.pk)["topic"])

    def test_patch_toggles_is_read_only(self):
        self.client.force_login(self.admin)
        response = self.patch(
            {"is_read": True, "name": "Changed", "email": "x@example.com", "service": "shop"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["is_read"])
        self.message.refresh_from_db()
        self.assertTrue(self.message.is_read)
        self.assertEqual(self.message.name, "Test Person")
        self.assertEqual(self.message.email, "test@example.com")
        self.assertEqual(self.message.service, self.web_apps)
        self.assertIsNone(self.message.project)
        response = self.patch({"is_read": False})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["is_read"])
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_read)

    def test_patch_requires_is_read(self):
        self.client.force_login(self.admin)
        response = self.patch({})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"is_read": ["This field is required."]})

    def test_no_create_delete_or_put(self):
        self.client.force_login(self.admin)
        detail = self.detail_url(self.message)
        payload = {"name": "Test Person", "email": "test@example.com", "message": "Hi", "is_read": True}
        self.assertEqual(
            self.client.post(self.list_url, payload, content_type="application/json").status_code, 405
        )
        self.assertEqual(self.client.put(detail, payload, content_type="application/json").status_code, 405)
        self.assertEqual(self.client.delete(detail).status_code, 405)
        self.assertEqual(self.client.get(detail).status_code, 405)
        self.assertEqual(ContactMessage.objects.count(), 1)
        self.message.refresh_from_db()
        self.assertFalse(self.message.is_read)

    def test_patch_needs_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        self.assertEqual(self.patch({"is_read": True}, client).status_code, 403)
        client.get("/api/dashboard/auth/me/")
        token = client.cookies["csrftoken"].value
        response = self.patch({"is_read": True}, client, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)


class ContactAdminTests(TestCase):
    def test_topic_is_listed_and_read_only(self):
        create_topics(self)
        admin_user = User.objects.create_superuser(email="admin@example.com", password="pass-12345")
        message = ContactMessage.objects.create(
            name="Test Person", email="test@example.com", message="Hi", service=self.web_apps
        )
        self.client.force_login(admin_user)
        response = self.client.get("/admin/contact/contactmessage/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "column-topic_display")
        self.assertContains(response, "Service: Web apps")
        response = self.client.get(f"/admin/contact/contactmessage/{message.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="service"')
        self.assertNotContains(response, 'name="project"')


class ContactTopicQaTests(TestCase):
    """Extra QA coverage: topic line in both channels and the admin topic filter."""

    def setUp(self):
        create_topics(self)

    @override_settings(CONTACT_NOTIFY_EMAIL="me@example.com")
    def test_email_body_has_topic_line(self):
        message = ContactMessage(
            name="Test Person", email="test@example.com", message="Hi", project=self.shop
        )
        _send_email(message)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Topic: Project: Shop\n", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].subject, "New contact message from Test Person")

    @override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_CHAT_ID="123")
    def test_telegram_text_has_topic_line(self):
        message = ContactMessage(
            name="Test Person", email="test@example.com", message="Hi", service=self.web_apps
        )
        with mock.patch("apps.contact.notifications.urlrequest.urlopen") as urlopen:
            _send_telegram(message)
        sent = json.loads(urlopen.call_args.args[0].data)
        self.assertIn("Topic: Service: Web apps\n", sent["text"])
        self.assertEqual(sent["chat_id"], "123")

    def test_admin_can_filter_by_topic(self):
        admin_user = User.objects.create_superuser(email="admin@example.com", password="pass-12345")
        ContactMessage.objects.create(
            name="Test Service", email="test@example.com", message="Hi", service=self.web_apps
        )
        ContactMessage.objects.create(
            name="Test Project", email="test@example.com", message="Hi", project=self.shop
        )
        ContactMessage.objects.create(name="Test None", email="test@example.com", message="Hi")
        self.client.force_login(admin_user)
        response = self.client.get(
            f"/admin/contact/contactmessage/?service__id__exact={self.web_apps.pk}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Service")
        self.assertNotContains(response, "Test Project")
        self.assertNotContains(response, "Test None")
        response = self.client.get(f"/admin/contact/contactmessage/?project__id__exact={self.shop.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Project")
        self.assertNotContains(response, "Test Service")
        # The related-only filter offers the topic titles that have messages.
        response = self.client.get("/admin/contact/contactmessage/")
        self.assertContains(response, "By service")
        self.assertContains(response, "By project")


class ContactTopicMigrationTests(TransactionTestCase):
    """Existing rows keep their data and get no topic after 0002."""

    before = [("contact", "0001_initial")]
    after = [("contact", "0002_contactmessage_topic")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_existing_rows_get_empty_topic(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old_apps = executor.loader.project_state(self.before).apps
        OldMessage = old_apps.get_model("contact", "ContactMessage")
        old = OldMessage.objects.create(
            name="Test Person", email="test@example.com", message="Hi", budget="2k_5k", is_read=True
        )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        new_apps = executor.loader.project_state(self.after).apps
        row = new_apps.get_model("contact", "ContactMessage").objects.get(pk=old.pk)
        self.assertIsNone(row.service_id)
        self.assertIsNone(row.project_id)
        self.assertEqual(
            (row.name, row.email, row.message, row.budget, row.is_read),
            ("Test Person", "test@example.com", "Hi", "2k_5k", True),
        )
