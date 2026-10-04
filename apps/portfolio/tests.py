from django.core.management import call_command
from django.test import TestCase

from .models import Project, Service, Technology


class ServiceApiTests(TestCase):
    def setUp(self):
        Service.objects.create(
            title="API", slug="api", summary="s", description="d", is_published=True
        )
        Service.objects.create(title="Draft", slug="draft", summary="s", is_published=False)

    def test_list_shows_only_published(self):
        response = self.client.get("/api/services/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["slug"] for item in response.json()], ["api"])

    def test_detail_of_unpublished_is_404(self):
        self.assertEqual(self.client.get("/api/services/draft/").status_code, 404)

    def test_detail_includes_description(self):
        self.assertEqual(self.client.get("/api/services/api/").json()["description"], "d")


class ProjectApiTests(TestCase):
    def setUp(self):
        django = Technology.objects.create(name="Django", slug="django")
        featured = Project.objects.create(
            title="A", slug="a", summary="s", problem="p", solution="so", result="r",
            is_featured=True, is_published=True,
        )
        featured.tech_stack.add(django)
        Project.objects.create(title="B", slug="b", summary="s", is_published=True)
        Project.objects.create(title="C", slug="c", summary="s", is_published=False)

    def test_list_hides_unpublished(self):
        slugs = {item["slug"] for item in self.client.get("/api/projects/").json()}
        self.assertEqual(slugs, {"a", "b"})

    def test_featured_filter(self):
        slugs = [item["slug"] for item in self.client.get("/api/projects/?featured=true").json()]
        self.assertEqual(slugs, ["a"])

    def test_list_has_no_case_study_text(self):
        item = self.client.get("/api/projects/").json()[0]
        self.assertNotIn("problem", item)

    def test_detail_has_case_study_and_technologies(self):
        data = self.client.get("/api/projects/a/").json()
        self.assertEqual(data["problem"], "p")
        self.assertEqual(data["result"], "r")
        self.assertEqual(data["tech_stack"][0]["slug"], "django")

    def test_detail_of_unpublished_is_404(self):
        self.assertEqual(self.client.get("/api/projects/c/").status_code, 404)


class InitialContentTests(TestCase):
    def test_fixture_loads_and_services_are_public(self):
        call_command("loaddata", "initial_content", verbosity=0)
        response = self.client.get("/api/services/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 7)
        self.assertEqual(Technology.objects.count(), 10)
