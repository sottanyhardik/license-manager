"""
Regression tests for URL routing changes in lmanagement/urls.py.

Three concerns pinned:
  A) ^media/ and ^assets/ serve() routes only appear when DEBUG=True at
     module import time.  Since tests run with DEBUG=False (default prod
     setting) those patterns must be absent.
  B) Any unmatched /api/... path returns JSON {"detail":"Not found."} 404.
  C) /api/schema/ permission wiring: [] when DEBUG=True, [IsAuthenticated]
     when DEBUG=False; and anonymous access is rejected in non-DEBUG mode.
"""
import inspect
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

import lmanagement.urls as root_urls

User = get_user_model()


class URLRoutingRegressionTests(APITestCase):
    """Regression tests for root urlconf routing changes."""

    def setUp(self):
        """Set up authenticated client and an anonymous client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="url_routing_testuser",
            email="url_routing@example.com",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)
        self.anon_client = APIClient()  # no credentials

    def tearDown(self):
        self.client.force_authenticate(user=None)

    # ------------------------------------------------------------------
    # Test A — DEBUG guard: ^media/ and ^assets/ serve() patterns
    # ------------------------------------------------------------------

    def test_debug_guard_source_structure(self):
        """
        ^media/ and ^assets/ serve() patterns must be inside an
        'if settings.DEBUG:' block in the root urlconf source.

        This is a whitebox guard: the Django test suite runs with
        DEBUG=False (the project default), so urlpatterns is already
        built without those patterns — but we also pin the source
        structure so a future refactor cannot accidentally move them
        outside the guard.
        """
        source = inspect.getsource(root_urls)

        self.assertIn(
            "if settings.DEBUG:",
            source,
            "Root urlconf must contain an 'if settings.DEBUG:' guard block",
        )

        debug_block_idx = source.index("if settings.DEBUG:")
        media_idx = source.index('"^media/')
        assets_idx = source.index('"^assets/')

        self.assertGreater(
            media_idx,
            debug_block_idx,
            "'^media/' serve pattern must appear after 'if settings.DEBUG:' guard",
        )
        self.assertGreater(
            assets_idx,
            debug_block_idx,
            "'^assets/' serve pattern must appear after 'if settings.DEBUG:' guard",
        )

    def test_media_serve_absent_when_debug_false(self):
        """
        When tests run with DEBUG=False (the project production default),
        no django.views.static.serve callback for a ^media/ route should
        be present in urlpatterns.
        """
        from django.conf import settings
        from django.views.static import serve

        # If DEBUG is True the test still passes vacuously — just
        # annotate so CI knows the real assertion was skipped.
        if settings.DEBUG:
            return  # guard not exercised in this environment; source test covers it

        media_serve_patterns = [
            p
            for p in root_urls.urlpatterns
            if getattr(p, "callback", None) is serve
            and "media" in (getattr(p.pattern, "_regex", "") or "")
        ]
        self.assertEqual(
            media_serve_patterns,
            [],
            "^media/ serve() route must not be in urlpatterns when DEBUG=False",
        )

    def test_assets_serve_absent_when_debug_false(self):
        """
        When tests run with DEBUG=False, no django.views.static.serve
        callback for a ^assets/ route should be present in urlpatterns.
        """
        from django.conf import settings
        from django.views.static import serve

        if settings.DEBUG:
            return

        assets_serve_patterns = [
            p
            for p in root_urls.urlpatterns
            if getattr(p, "callback", None) is serve
            and "assets" in (getattr(p.pattern, "_regex", "") or "")
        ]
        self.assertEqual(
            assets_serve_patterns,
            [],
            "^assets/ serve() route must not be in urlpatterns when DEBUG=False",
        )

    def test_serve_import_exists_in_urlconf(self):
        """serve must still be imported (needed for DEBUG=True); confirms
        the import line itself hasn't been removed."""
        source = inspect.getsource(root_urls)
        self.assertIn(
            "from django.views.static import serve",
            source,
            "serve import must remain in root urlconf",
        )

    # ------------------------------------------------------------------
    # Test B — Unmatched /api/... paths return JSON 404
    # ------------------------------------------------------------------

    def test_api_unknown_path_returns_json_404_authenticated(self):
        """
        Authenticated request to a non-existent /api/ path must get
        HTTP 404 with JSON body {"detail": "Not found."}.
        """
        response = self.client.get("/api/this-path-definitely-does-not-exist-xyz/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        self.assertEqual(
            data.get("detail"),
            "Not found.",
            f"Expected {{\"detail\": \"Not found.\"}}, got {data!r}",
        )

    def test_api_unknown_path_returns_json_404_anonymous(self):
        """
        Anonymous request to a non-existent /api/ path must also get
        HTTP 404 with JSON body — the _api_404 view is auth-agnostic.
        """
        response = self.anon_client.get("/api/totally-unknown-endpoint-abc123/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        self.assertEqual(
            data.get("detail"),
            "Not found.",
            f"Expected {{\"detail\": \"Not found.\"}}, got {data!r}",
        )

    def test_api_unknown_path_content_type_is_json(self):
        """
        The _api_404 handler must return application/json, not HTML.
        """
        response = self.anon_client.get("/api/no-such-view-here/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        content_type = response.get("Content-Type", "")
        self.assertIn(
            "application/json",
            content_type,
            f"Expected application/json content-type, got {content_type!r}",
        )

    def test_html_404_template_renders_without_external_assets(self):
        """
        The production Django 404 template must render standalone without
        relying on stale DAdmin assets, external fonts, or JavaScript.
        """
        rendered = get_template("404.html").render({})

        self.assertIn("Page not found", rendered)
        self.assertIn('href="/"', rendered)
        self.assertIn('name="robots"', rendered)
        self.assertNotIn("fonts.googleapis.com", rendered)
        self.assertNotIn("assets/js/", rendered)
        self.assertNotIn("assets/css/", rendered)

    def test_html_500_template_renders_without_external_assets(self):
        """
        The production Django 500 template must render standalone without
        context, external fonts, or JavaScript.
        """
        rendered = get_template("500.html").render({})

        self.assertIn("Something went wrong", rendered)
        self.assertIn('href="/"', rendered)
        self.assertIn('name="robots"', rendered)
        self.assertNotIn("fonts.googleapis.com", rendered)
        self.assertNotIn("assets/js/", rendered)
        self.assertNotIn("assets/css/", rendered)

    def test_api_catchall_pattern_exists_in_urlpatterns(self):
        """
        A ^api/ regex pattern with callback _api_404 must be present in
        urlpatterns, positioned before the SPA catch-all.
        """
        api_catchall = next(
            (
                p
                for p in root_urls.urlpatterns
                if getattr(p, "callback", None) is root_urls._api_404
            ),
            None,
        )
        self.assertIsNotNone(
            api_catchall,
            "_api_404 catch-all pattern must be present in urlpatterns",
        )

        # Must appear before the SPA catch-all (^.*$)
        api_idx = root_urls.urlpatterns.index(api_catchall)
        spa_pattern = root_urls.urlpatterns[-1]  # SPA is always last
        spa_idx = root_urls.urlpatterns.index(spa_pattern)
        self.assertLess(
            api_idx,
            spa_idx,
            "_api_404 must be positioned before the SPA catch-all in urlpatterns",
        )

    def test_spa_catchall_resolves_react_entry_template(self):
        """
        The SPA catch-all must resolve to the built React entry, not a
        stale backend demo template named index.html.
        """
        template = get_template("index.html")
        origin_name = Path(template.origin.name).resolve()
        expected = (settings.BASE_DIR.parent / "frontend" / "dist" / "index.html").resolve()

        self.assertEqual(origin_name, expected)

    def test_api_unknown_path_post_returns_json_404(self):
        """
        POST to an unmatched /api/ path must also return JSON 404
        (not a 405 Method Not Allowed, because _api_404 handles all methods).
        """
        response = self.anon_client.post(
            "/api/no-such-resource/",
            data={"key": "value"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        self.assertEqual(data.get("detail"), "Not found.")

    # ------------------------------------------------------------------
    # Test C — /api/schema/ permission wiring
    # ------------------------------------------------------------------

    def test_schema_pattern_exists(self):
        """A URL pattern named 'schema' must exist in urlpatterns."""
        schema_pattern = next(
            (p for p in root_urls.urlpatterns if getattr(p, "name", None) == "schema"),
            None,
        )
        self.assertIsNotNone(schema_pattern, "URL pattern named 'schema' must exist")

    def test_schema_permission_class_wiring_matches_debug_flag(self):
        """
        The permission_classes wired into SpectacularAPIView must match
        the DEBUG setting captured at module import time:
          - DEBUG=True  -> permission_classes == []
          - DEBUG=False -> permission_classes == [IsAuthenticated]
        """
        from django.conf import settings
        from rest_framework.permissions import IsAuthenticated

        schema_pattern = next(
            (p for p in root_urls.urlpatterns if getattr(p, "name", None) == "schema"),
            None,
        )
        self.assertIsNotNone(schema_pattern)

        initkwargs = getattr(schema_pattern.callback, "initkwargs", {})
        permission_classes = initkwargs.get("permission_classes", None)

        if settings.DEBUG:
            self.assertEqual(
                permission_classes,
                [],
                "In DEBUG mode, schema permission_classes must be []",
            )
        else:
            self.assertIsNotNone(
                permission_classes,
                "In non-DEBUG mode, permission_classes must be set on schema view",
            )
            self.assertIn(
                IsAuthenticated,
                permission_classes,
                "In non-DEBUG mode, IsAuthenticated must guard /api/schema/",
            )

    def test_schema_endpoint_rejects_anonymous_when_not_debug(self):
        """
        When DEBUG=False (non-debug / production mode), an unauthenticated
        GET to /api/schema/ must be rejected with 401 or 403.
        When DEBUG=True the endpoint is open; it must not 500.
        """
        from django.conf import settings

        response = self.anon_client.get("/api/schema/")

        if not settings.DEBUG:
            self.assertIn(
                response.status_code,
                [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
                (
                    "Anonymous /api/schema/ must be 401 or 403 in production mode, "
                    f"got {response.status_code}"
                ),
            )
        else:
            self.assertNotEqual(
                response.status_code,
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "/api/schema/ must not 500 in DEBUG mode",
            )

    def test_schema_endpoint_accessible_when_authenticated_and_not_debug(self):
        """
        An authenticated user must be able to reach /api/schema/ even in
        non-DEBUG mode (IsAuthenticated, not IsAdminUser).
        """
        from django.conf import settings

        response = self.client.get("/api/schema/")

        if not settings.DEBUG:
            # Authenticated user should get 200 (YAML/JSON schema blob)
            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                (
                    "Authenticated /api/schema/ must be 200 in production mode, "
                    f"got {response.status_code}"
                ),
            )
        else:
            self.assertNotEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_schema_permission_variable_used_in_source(self):
        """
        The module-level _schema_permission variable must be referenced
        in the urlpatterns definition (not a hard-coded literal), so the
        branching stays DRY and testable.
        """
        source = inspect.getsource(root_urls)
        self.assertIn(
            "_schema_permission",
            source,
            "_schema_permission variable must be defined and used in root urlconf",
        )
        # It must be derived from settings.DEBUG
        self.assertIn(
            "settings.DEBUG",
            source,
            "_schema_permission must branch on settings.DEBUG",
        )
