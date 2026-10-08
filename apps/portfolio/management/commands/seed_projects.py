"""Create or update the first three portfolio projects (idempotent).

Usage:  python manage.py seed_projects
All projects are saved as drafts (is_published=False). Publish them in the admin
once client / co-founder permission is confirmed, and upload cover images there.
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.portfolio.models import Project, Technology

SPECIAL_SLUGS = {"shadcn/ui": "shadcn-ui", "ESC/POS": "esc-pos"}

PROJECTS = [
    {
        "slug": "fammo-ai-pet-nutrition-platform",
        "title": "FAMMO.ai: AI Pet Nutrition Platform (Django REST API + Next.js)",
        "client_name": "",
        "summary": (
            "FAMMO.ai is an AI pet nutrition and health platform for the Dutch and Belgian market. "
            "As co-founder and CTO, I rebuilt it from a Django monolith into a DRF API with two "
            "Next.js apps, and built its AI features and forum, with a food label scanner in progress."
        ),
        "problem": """FAMMO started as a multilingual pet content site on a Django monolith hosted on cPanel. Background jobs such as Celery were hard to run there, and the old setup could not support the product the team wanted to build: personalised pet nutrition, AI health reports and a vet directory for pet owners in the Netherlands and Belgium.

The team needed a backend that could serve a public website, an internal admin console and later a mobile app, plus infrastructure that could run Redis, Celery and a mail server without workarounds.""",
        "solution": """I moved the product into three separate repositories and a Docker-based VPS setup:

- **Backend:** Django REST Framework API under `/api/v1/`, PostgreSQL, JWT authentication with refresh, role-based access (eight user roles), Celery and Redis for background work.
- **Public website:** Next.js (App Router, TypeScript, Tailwind CSS, Zustand) with a dual-zone design system: amber for nutrition, sage for health.
- **Admin console:** an internal Next.js app for users, pets, clinics, subscriptions, branding and a blog editor built on Tiptap.

Key decisions and features:

- Moved the data from SQLite to PostgreSQL, then removed the old central `api` app and placed API code inside each domain app.
- Tested 74 API endpoints and fixed five bugs found in that pass, including silent data loss on pet creation and blocking Telegram notifications.
- Built NURNO, an AI assistant for pet health and nutrition, plus AI meal plans and AI health reports using the OpenAI API, with plan-based usage limits.
- Built a pet profile wizard, a vet directory with a map and appointment booking, and the PawTalk community forum.
- Added FAQPage structured data across the site, including an automatic parser for FAQ sections in about 70 published blog posts.
- Started a Food Photo Scanner: a user photographs a pet food label and the AI judges it against the pet's profile, using a shared product catalog and an admin review flow. Backend and API are built; the interface is in active development.
- Deployed everything with Docker Compose behind Nginx, with Gunicorn, Celery, Redis and a self-hosted mail server for transactional email.""",
        "result": """The new platform is live on its own VPS and serves the public site, the admin console and the API. More than 2,000 registered accounts and 300+ pet profiles were carried over through the data migration.

After launch I audited the sign-up paths and fixed broken links, and the product keeps improving every week, with the Food Photo Scanner interface as the next feature to ship.""",
        "tech": [
            "Django", "Django REST Framework", "PostgreSQL", "Redis", "Celery", "Next.js",
            "TypeScript", "Tailwind CSS", "Zustand", "shadcn/ui", "Tiptap", "JWT",
            "OpenAI API", "Docker Compose", "Nginx", "Gunicorn", "Google Analytics 4",
        ],
        "live_url": "https://fammo.ai",
        "order": 0,
        "is_featured": True,
    },
    {
        "slug": "jovira-travel-agency-platform",
        "title": "Jovira: Travel Agency Operations Platform",
        "client_name": "Jovira Travel Agency",
        "summary": (
            "Self-hosted operations platform for a start-up travel agency: reservations, hotel and tour "
            "inventory, agency and public pricing, an internal Work Desk and financial reports. Includes "
            "a public website and an agency portal, built as a Django REST API with two Next.js apps."
        ),
        "problem": """Jovira Travel Agency is a start-up that needed one system to run its daily operations: reservations, hotel and tour inventory, pricing, internal task handover between staff, and management reporting.

The agency also sells through two channels with different prices: **approved partner agencies** and **the general public**. The system had to keep these strictly separated, support English, Russian and Turkish, and be fully self-hosted with no third-party SaaS.""",
        "solution": """The platform is split into three separate repositories, each with its own concerns:

- **Backend:** Django REST Framework API on PostgreSQL with JWT authentication and role-based access control.
- **Admin panel:** Next.js (App Router, TypeScript) for staff: reservation grid, inventory, Work Desk and reports.
- **Public website:** Next.js site with hotel and tour search, booking requests and an agency portal.

Key decisions:

- **Pricing:** every sellable item has a public and an agency price. Approved agencies see the agency price, everyone else sees the public price, and an unapproved agency never sees agency pricing. If no public price is set, the site shows "Price on request" and the customer can still submit a request.
- **Website bookings:** requests from the site create a real reservation in the same admin grid, so staff work in one place. Visitors are linked to an existing customer by email, and accounts are never created automatically.
- **Reservation numbers:** generated server-side as a year-based sequence (for example JV2609-00001), so staff can tell reservations apart easily.
- **Work Desk:** a four-panel internal workspace (pins, reminders, received requests, sent requests) for handing work between departments. Sender fields are set on the server and cannot be spoofed.
- **Tour inventory:** one tour holds a rate matrix (duration, hotel star category, room type) with a mandatory validity period on each rate.
- **Hotel special offers:** date-range pricing that applies automatically to a matching stay and falls back to the standard room price when a value is empty.
- **Reporting:** a management reports module with eight tabs and CSV export, restricted to admin and finance roles.
- **Internationalisation:** English, Russian and Turkish in both frontends, with a script that checks all translation files stay in sync.
- **Deployment:** Docker and Docker Compose on a single VPS behind Nginx with Let's Encrypt SSL. PostgreSQL runs on the host, outside Docker, so backups stay independent.""",
        "result": """The three applications went into production on 12 September 2026 and run over HTTPS on separate subdomains for the public site, the admin panel and the API.

The main flows were tested end to end, from hotel search and booking as an anonymous visitor and as an agency through to the resulting reservation in the admin grid.

The client keeps adding features, including tour rate matrices, special offers and room availability indicators, and real inventory is being entered into the live system.

**Still planned:** voucher generation, cancellation and approval actions, and reservation amendments.""",
        "tech": [
            "Django", "Django REST Framework", "PostgreSQL", "SimpleJWT", "Next.js", "React",
            "TypeScript", "TanStack Query", "TanStack Table", "Tailwind CSS", "Zod", "Axios",
            "next-intl", "Gunicorn", "Docker", "Docker Compose", "Nginx", "Let's Encrypt",
        ],
        "live_url": "https://joviratravel.com",
        "order": 1,
        "is_featured": True,
    },
    {
        "slug": "damo-restaurant-pos-system",
        "title": "Restaurant POS and Multilingual Menu System (Django REST + Next.js)",
        "client_name": "Damo restaurant",
        "summary": (
            "A custom point-of-sale, inventory and reporting system, plus a four-language public menu, "
            "for a Persian restaurant in Turkey. Built with Django REST Framework and Next.js to replace "
            "an existing SambaPOS setup."
        ),
        "problem": """The restaurant, a Persian restaurant in Turkey, needed a custom system built around its own workflow to replace its SambaPOS setup. The system had to cover a cashier screen, stock tracking based on recipes, sales reporting, and a public menu in four languages (Turkish, English, Arabic and Persian).

Two requirements made the project more than routine. Printing had to work across two very different devices: a network thermal kitchen printer on an isolated local network that a cloud server cannot reach, and a USB receipt printer attached to the cashier's computer. Stock also had to be deducted per dish through recipes (for example, one kebab plate consumes specific skewers), not per item sold.""",
        "solution": """**Three independent parts**, each deployed on its own:

- A Django REST Framework API on PostgreSQL
- A Next.js admin application for the POS and management screens
- A separate Next.js public menu

**Key technical decisions:**

- **Access control:** email-based login with JWT (10-hour access tokens to match a shift, 7-day refresh tokens). Roles are owner, manager, cashier and staff. Inventory and reports are restricted to managers and owners.
- **Recipe-based inventory:** an append-only stock ledger, so current stock is always computed from recorded movements. Stock is deducted only when an order is completed, through recipe lines. The menu app is display-only and holds no inventory logic.
- **Four languages without third-party i18n libraries:** per-language translation tables served through a `?lang=` parameter with an English fallback. The admin forms support right-to-left input for Arabic and Persian.
- **Multi-currency payments:** cash in TRY, USD and EUR plus card payments, with an exchange-rate snapshot stored on each order. The system distinguishes a pre-payment bill from a post-payment receipt.
- **Printing through a job queue:** the first design used a local agent that only accepted requests from the POS computer, so orders placed from phones did not print. It was replaced by a print-job queue in the API. A small Windows agent on the POS computer polls the queue using a shared secret and forwards ticket data to the kitchen printer. Jobs expire after a configurable time. The USB receipt printer uses browser kiosk printing with a layout tuned for 72 mm thermal paper. Printer settings can be changed from the admin panel.
- **Deployment:** Ubuntu 24.04 VPS with Gunicorn, Nginx, PM2 and HTTPS through Certbot. Changes go through Git only, followed by migrate, build and restart.""",
        "result": """All three parts are built and running on a production server.

- **POS and management:** table map, order screen, multi-currency payment, inventory and stock ledger, reports, user management, and menu management with four-language forms and image upload.
- **Public menu:** available in Turkish, English, Arabic and Persian. Old printed QR-code links redirect to the new menu.
- **Printing:** kitchen ticket printing was tested end to end on the live system. An order placed from a mobile device was printed in the kitchen and its print job completed.""",
        "tech": [
            "Django", "Django REST Framework", "PostgreSQL", "Next.js", "TypeScript",
            "Tailwind CSS", "JWT", "ESC/POS", "Python", "PyInstaller", "Gunicorn", "Nginx",
            "PM2", "Certbot", "Ubuntu",
        ],
        "live_url": "https://damorestaurant.com",
        "order": 2,
        "is_featured": True,
    },
]


class Command(BaseCommand):
    help = "Create or update the first three portfolio projects as drafts."

    def handle(self, *args, **options):
        for data in PROJECTS:
            data = dict(data)
            tech_names = data.pop("tech")
            slug = data.pop("slug")
            project, created = Project.objects.update_or_create(
                slug=slug, defaults={**data, "is_published": False}
            )
            techs = []
            for name in tech_names:
                tech = Technology.objects.filter(name=name).first()
                if tech is None:
                    tech = Technology.objects.create(
                        name=name, slug=SPECIAL_SLUGS.get(name, slugify(name))
                    )
                techs.append(tech)
            project.tech_stack.set(techs)
            self.stdout.write(f"{'Created' if created else 'Updated'}: {project.title}")
