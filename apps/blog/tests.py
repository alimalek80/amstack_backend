import shutil
import tempfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from .models import Category, Post

User = get_user_model()


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

    def test_image_upload_and_cover(self):
        buffer = BytesIO()
        Image.new("RGB", (4, 4), "red").save(buffer, "PNG")
        upload = SimpleUploadedFile("shot.png", buffer.getvalue(), content_type="image/png")
        image = self.client.post("/api/dashboard/images/", {"image": upload}).json()
        self.assertTrue(image["url"].startswith("/media/blog/"))
        post = self.create(cover=image["id"]).json()
        self.assertEqual(post["cover_url"], image["url"])
