import shutil
import tempfile
import threading
from io import BytesIO
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    TransactionTestCase,
    override_settings,
)
from PIL import Image
from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle

from .models import Category, Post
from .views import BOT_UA_MARKERS, is_bot

User = get_user_model()

BROWSER_UA = "Mozilla/5.0 (X11; Linux x86_64) Firefox/131.0"


def doc(*nodes):
    return {"type": "doc", "content": list(nodes)}


def code_block(code, language="python"):
    return {"type": "codeBlock", "attrs": {"language": language}, "content": [{"type": "text", "text": code}]}


class PublicBlogApiTests(TestCase):
    def setUp(self):
        self.django = Category.objects.create(name="Django", slug="django")
        Category.objects.create(name="Empty", slug="empty")
        Post.objects.create(
            title="Live", slug="live", category=self.django, is_published=True,
            body=doc(code_block("print(1)")),
        )
        Post.objects.create(title="Draft", slug="draft", category=self.django)

    def test_list_shows_only_published(self):
        slugs = [p["slug"] for p in self.client.get("/api/blog/posts/").json()]
        self.assertEqual(slugs, ["live"])

    def test_list_filters_by_category(self):
        self.assertEqual(self.client.get("/api/blog/posts/?category=nope").json(), [])
        self.assertEqual(len(self.client.get("/api/blog/posts/?category=django").json()), 1)

    def test_detail_has_body_and_draft_is_404(self):
        data = self.client.get("/api/blog/posts/live/").json()
        self.assertEqual(data["body"]["content"][0]["attrs"]["language"], "python")
        self.assertIsNotNone(data["published_at"])
        self.assertEqual(self.client.get("/api/blog/posts/draft/").status_code, 404)

    def test_categories_only_with_published_posts(self):
        data = self.client.get("/api/blog/categories/").json()
        self.assertEqual([(c["slug"], c["post_count"]) for c in data], [("django", 1)])


class PostViewCountTests(TestCase):
    def setUp(self):
        cache.clear()
        self.live = Post.objects.create(title="Live", slug="live", is_published=True)
        self.draft = Post.objects.create(title="Draft", slug="draft")

    def view(self, slug="live", **headers):
        return self.client.post(f"/api/blog/posts/{slug}/view/", **headers)

    def test_view_increments_published_post(self):
        self.assertEqual(self.view(HTTP_USER_AGENT=BROWSER_UA).json(), {"view_count": 1})
        self.assertEqual(self.view(HTTP_USER_AGENT=BROWSER_UA).json(), {"view_count": 2})
        self.live.refresh_from_db()
        self.assertEqual(self.live.view_count, 2)

    def test_view_404_for_draft_and_missing(self):
        self.assertEqual(self.view("draft", HTTP_USER_AGENT=BROWSER_UA).status_code, 404)
        self.assertEqual(self.view("nope", HTTP_USER_AGENT=BROWSER_UA).status_code, 404)
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.view_count, 0)

    def test_bot_and_empty_user_agent_do_not_count(self):
        for ua in ("Googlebot/2.1", "HeadlessChrome/120", "Chrome-Lighthouse"):
            response = self.view(HTTP_USER_AGENT=ua)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"view_count": 0})
        response = self.view()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"view_count": 0})
        self.live.refresh_from_db()
        self.assertEqual(self.live.view_count, 0)

    def test_detail_get_does_not_count(self):
        self.client.get("/api/blog/posts/live/", HTTP_USER_AGENT=BROWSER_UA)
        data = self.client.get("/api/blog/posts/live/", HTTP_USER_AGENT=BROWSER_UA).json()
        self.assertNotIn("view_count", data)
        self.assertNotIn("view_count", self.client.get("/api/blog/posts/").json()[0])
        self.live.refresh_from_db()
        self.assertEqual(self.live.view_count, 0)

    def test_get_is_not_allowed(self):
        response = self.client.get("/api/blog/posts/live/view/", HTTP_USER_AGENT=BROWSER_UA)
        self.assertEqual(response.status_code, 405)

    def test_view_keeps_updated_at(self):
        updated_at = self.live.updated_at
        self.view(HTTP_USER_AGENT=BROWSER_UA)
        self.live.refresh_from_db()
        self.assertEqual(self.live.updated_at, updated_at)
        self.assertEqual(self.live.view_count, 1)

    def test_view_is_throttled(self):
        # DRF caches rates on the class, so override_settings does not reach them.
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"blog_view": "2/hour"}):
            self.assertEqual(self.view(HTTP_USER_AGENT=BROWSER_UA).status_code, 200)
            self.assertEqual(self.view(HTTP_USER_AGENT=BROWSER_UA).status_code, 200)
            self.assertEqual(self.view(HTTP_USER_AGENT=BROWSER_UA).status_code, 429)
        self.live.refresh_from_db()
        self.assertEqual(self.live.view_count, 2)


@override_settings(CSRF_TRUSTED_ORIGINS=["https://amstack.org"])
class PostViewCountOriginTests(TestCase):
    """Only same-origin browser requests count, so other sites cannot inflate views."""

    def setUp(self):
        cache.clear()
        self.live = Post.objects.create(title="Live", slug="live", is_published=True)

    def view(self, **headers):
        return self.client.post("/api/blog/posts/live/view/", HTTP_USER_AGENT=BROWSER_UA, **headers)

    def assert_not_counted(self, **headers):
        response = self.view(**headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"view_count": 0})
        self.live.refresh_from_db()
        self.assertEqual(self.live.view_count, 0)

    def test_cross_site_fetch_does_not_count(self):
        for site in ("cross-site", "same-site", "none"):
            self.assert_not_counted(HTTP_SEC_FETCH_SITE=site)

    def test_foreign_origin_does_not_count(self):
        self.assert_not_counted(HTTP_ORIGIN="https://evil.example")
        self.assert_not_counted(HTTP_ORIGIN="null")
        # A same-origin Sec-Fetch-Site does not excuse a foreign Origin.
        self.assert_not_counted(HTTP_SEC_FETCH_SITE="same-origin", HTTP_ORIGIN="https://evil.example")

    def test_same_origin_and_no_headers_count(self):
        self.assertEqual(
            self.view(HTTP_SEC_FETCH_SITE="same-origin", HTTP_ORIGIN="https://amstack.org").json(),
            {"view_count": 1},
        )
        self.assertEqual(self.view(HTTP_SEC_FETCH_SITE="same-origin").json(), {"view_count": 2})
        self.assertEqual(self.view(HTTP_ORIGIN="https://amstack.org").json(), {"view_count": 3})
        self.assertEqual(self.view().json(), {"view_count": 4})


class BotUserAgentTests(SimpleTestCase):
    def test_every_marker_matches_in_any_case(self):
        for marker in BOT_UA_MARKERS:
            embedded = f"Mozilla/5.0 (compatible; X{marker.title()}/1.0)"
            for ua in (marker, marker.upper(), marker.capitalize(), embedded):
                with self.subTest(ua=ua):
                    self.assertTrue(is_bot(ua))

    def test_empty_user_agent_is_a_bot(self):
        self.assertTrue(is_bot(""))

    def test_real_browser_is_not_a_bot(self):
        chrome = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        )
        for ua in (chrome, BROWSER_UA):
            with self.subTest(ua=ua):
                self.assertFalse(is_bot(ua))


class ThrottleClientIpTests(SimpleTestCase):
    """Guards the proxy assumption: nginx then Caddy in front of Gunicorn (NUM_PROXIES=2)."""

    def test_two_proxies_take_the_real_client_ip(self):
        rest_framework = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 2}
        # get_ident() reads the module-level api_settings, which caches values. override_settings
        # fires setting_changed and DRF calls api_settings.reload(), so the override reaches it
        # (unlike THROTTLE_RATES, a class attribute frozen at import). The assert proves it.
        with override_settings(REST_FRAMEWORK=rest_framework):
            self.assertEqual(api_settings.NUM_PROXIES, 2)
            request = RequestFactory().post(
                "/api/blog/posts/live/view/",
                HTTP_X_FORWARDED_FOR="6.6.6.6, 1.2.3.4, 172.18.0.5",
                REMOTE_ADDR="172.18.0.9",
            )
            self.assertEqual(ScopedRateThrottle().get_ident(request), "1.2.3.4")


class PostViewCountConcurrencyTests(TransactionTestCase):
    """Real threads and real connections, so lost updates would show up (acceptance 3)."""

    # 40 requests from one IP: lift the rate so a future change to blog_view cannot fail this test.
    @mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"blog_view": "10000/hour"})
    def test_parallel_views_are_not_lost(self):
        cache.clear()
        post = Post.objects.create(title="Live", slug="live", is_published=True)
        threads, per_thread = 8, 5
        barrier = threading.Barrier(threads)
        statuses = []

        def worker():
            client = Client()
            try:
                barrier.wait()
                for _ in range(per_thread):
                    statuses.append(
                        client.post("/api/blog/posts/live/view/", HTTP_USER_AGENT=BROWSER_UA).status_code
                    )
            finally:
                connection.close()

        pool = [threading.Thread(target=worker) for _ in range(threads)]
        for thread in pool:
            thread.start()
        for thread in pool:
            thread.join()

        self.assertEqual(statuses, [200] * threads * per_thread)
        post.refresh_from_db()
        self.assertEqual(post.view_count, threads * per_thread)


class PostAdminViewCountTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="pass-12345")
        self.client.force_login(self.admin)
        self.post = Post.objects.create(title="Live", slug="live", is_published=True, view_count=7)

    def test_admin_list_shows_view_count(self):
        response = self.client.get("/admin/blog/post/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "column-view_count")
        self.assertContains(response, '<td class="field-view_count">7</td>', html=True)

    def test_admin_change_page_view_count_is_read_only(self):
        response = self.client.get(f"/admin/blog/post/{self.post.pk}/change/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "field-view_count")
        self.assertNotContains(response, 'name="view_count"')


class DashboardAuthTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(email="admin@example.com", password="pass-12345")
        User.objects.create_user(email="staff@example.com", password="pass-12345", is_staff=True)

    def test_login_requires_superuser(self):
        bad = self.client.post(
            "/api/dashboard/auth/login/",
            {"email": "staff@example.com", "password": "pass-12345"},
            content_type="application/json",
        )
        self.assertEqual(bad.status_code, 400)
        ok = self.client.post(
            "/api/dashboard/auth/login/",
            {"email": "ADMIN@example.com", "password": "pass-12345"},
            content_type="application/json",
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard/auth/me/").json()["email"], "admin@example.com")

    def test_dashboard_closed_to_anonymous_and_staff(self):
        self.assertEqual(self.client.get("/api/dashboard/posts/").status_code, 403)
        self.client.login(email="staff@example.com", password="pass-12345")
        self.assertEqual(self.client.get("/api/dashboard/posts/").status_code, 403)

    def test_writes_need_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post("/api/dashboard/categories/", {"name": "Go"}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        client.get("/api/dashboard/auth/me/")
        token = client.cookies["csrftoken"].value
        response = client.post(
            "/api/dashboard/categories/", {"name": "Go"},
            content_type="application/json", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["slug"], "go")


TEMP_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class DashboardPostTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        admin = User.objects.create_superuser(email="admin@example.com", password="pass-12345")
        self.client.force_login(admin)

    def create(self, **data):
        payload = {"title": "Hello Django", "body": doc(), **data}
        return self.client.post("/api/dashboard/posts/", payload, content_type="application/json")

    def test_detail_has_category_name_even_without_category(self):
        data = self.create().json()
        self.assertIsNone(data["category_name"])
        category = Category.objects.create(name="Go", slug="go")
        response = self.client.patch(
            f"/api/dashboard/posts/{data['id']}/", {"category": category.id}, content_type="application/json"
        )
        self.assertEqual(response.json()["category_name"], "Go")

    def test_create_generates_unique_slug(self):
        self.assertEqual(self.create().json()["slug"], "hello-django")
        self.assertEqual(self.create().json()["slug"], "hello-django-2")

    def test_body_is_cleaned(self):
        body = doc(
            {"type": "codeBlock", "attrs": {"language": "Python", "class": "x"},
             "content": [{"type": "text", "text": "x = 1"}]},
            {"type": "heading", "attrs": {"level": 9}, "content": [{"type": "text", "text": "Setup"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "Docs", "marks": [
                {"type": "link", "attrs": {"href": "https://docs.djangoproject.com", "target": "_blank"}},
                {"type": "highlight"}]}]},
        )
        data = self.create(body=body).json()["body"]["content"]
        self.assertEqual(data[0], code_block("x = 1"))
        self.assertEqual(data[1]["attrs"], {"level": 2})
        self.assertEqual(data[2]["content"][0]["marks"][0], {"type": "link", "attrs": {"href": "https://docs.djangoproject.com"}})

    def test_rejects_unknown_nodes_and_unsafe_urls(self):
        self.assertEqual(self.create(body=[{"type": "text"}]).status_code, 400)
        self.assertEqual(self.create(body=doc({"type": "script"})).status_code, 400)
        bad_image = doc({"type": "image", "attrs": {"src": "javascript:alert(1)"}})
        self.assertEqual(self.create(body=bad_image).status_code, 400)
        bad_link = doc({"type": "paragraph", "content": [
            {"type": "text", "text": "x", "marks": [{"type": "link", "attrs": {"href": "javascript:alert(1)"}}]}]})
        self.assertEqual(self.create(body=bad_link).status_code, 400)

    def test_tables_are_kept(self):
        cell = lambda kind, text: {  # noqa: E731
            "type": kind, "attrs": {"colspan": 1, "rowspan": 1, "colwidth": None},
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}
        table = doc({"type": "table", "content": [
            {"type": "tableRow", "content": [cell("tableHeader", "Part"), cell("tableHeader", "Job")]},
            {"type": "tableRow", "content": [cell("tableCell", "Model"), cell("tableCell", "Data")]},
        ]})
        body = self.create(body=table).json()["body"]["content"][0]
        self.assertEqual(body["content"][0]["content"][0]["attrs"], {"colspan": 1, "rowspan": 1})
        self.assertEqual(body["content"][1]["content"][1]["type"], "tableCell")

    def test_reading_time_counts_all_text(self):
        words = " ".join(["word"] * 600)
        body = doc({"type": "paragraph", "content": [{"type": "text", "text": words}]})
        self.assertEqual(self.create(body=body).json()["reading_minutes"], 3)

    def test_publish_sets_date_and_shows_publicly(self):
        post_id = self.create().json()["id"]
        self.client.patch(
            f"/api/dashboard/posts/{post_id}/", {"is_published": True}, content_type="application/json"
        )
        self.assertEqual(Client().get("/api/blog/posts/hello-django/").status_code, 200)

    def test_list_has_read_only_view_count(self):
        post_id = self.create().json()["id"]
        self.assertEqual(self.client.get("/api/dashboard/posts/").json()[0]["view_count"], 0)
        response = self.client.patch(
            f"/api/dashboard/posts/{post_id}/", {"view_count": 99}, content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("view_count", response.json())
        self.assertEqual(Post.objects.get(pk=post_id).view_count, 0)

    def test_image_upload_and_cover(self):
        buffer = BytesIO()
        Image.new("RGB", (4, 4), "red").save(buffer, "PNG")
        upload = SimpleUploadedFile("shot.png", buffer.getvalue(), content_type="image/png")
        image = self.client.post("/api/dashboard/images/", {"image": upload}).json()
        self.assertTrue(image["url"].startswith("/media/blog/"))
        post = self.create(cover=image["id"]).json()
        self.assertEqual(post["cover_url"], image["url"])
