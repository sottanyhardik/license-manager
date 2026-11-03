"""
Dashboard API View (v3). Contract: docs/09-module-implementation/dashboard.md §4.

Role-gated sections are built by `apps.license.services.dashboard_summary`.
This view only parses the scope, serves and fills the cache, and maps bad
input to 400.
"""
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.cache_utils import CACHE_TIMEOUT_MEDIUM
from apps.core.models import CompanyModel
from apps.core.utils.exceptions import api_error
from apps.license.services import dashboard_summary as summary

# Bump when the payload shape changes so payloads cached before the change are not served.
# `view:dashboard*` keys are cleared by the existing invalidation hooks.
CACHE_VERSION = "v4"


def _optional_date(value, name):
    if value in (None, ""):
        return None
    try:
        parsed = parse_date(value)
    except ValueError:
        parsed = None
    if parsed is None:
        raise ValueError(f"{name} must be a valid YYYY-MM-DD date.")
    return parsed


class DashboardDataView(APIView):
    """
    Unified dashboard endpoint.

    Query parameters (all optional): `company_id`, `date_from`, `date_to`
    (activity window, inclusive), `refresh=1` (skip the cached read; the
    fresh result is still cached).

    Any authenticated user can reach the endpoint. Sections are returned
    only for the roles that grant them, and never as zero-filled stand-ins.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            scope = self._scope(request.query_params)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=400)

        user = request.user
        if "section" in request.query_params:
            return self._single_section(user, scope, request.query_params["section"])

        roles_key = "superuser" if user.is_superuser else "_".join(sorted(user.get_role_codes()))
        cache_key = f"view:dashboard:{CACHE_VERSION}:{roles_key}:{scope.cache_token}"

        if request.query_params.get("refresh") != "1":
            cached = cache.get(cache_key)
            if cached is not None:
                return Response({**cached, "meta": {**cached["meta"], "cached": True}})

        try:
            generated_at = timezone.now()
            sections = summary.build_dashboard_payload(user, scope)
            payload = {
                "meta": summary.build_meta(scope, cached=False, generated_at=generated_at),
                **sections,
            }
        except Exception as exc:
            return Response(api_error("Failed to load dashboard data", exc, __name__), status=500)

        # A payload with a failed section is served but not cached: the next request should retry it.
        if not summary.has_error(payload):
            cache.set(cache_key, payload, CACHE_TIMEOUT_MEDIUM)
        return Response(payload)

    @staticmethod
    def _single_section(user, scope, name):
        """
        `?section=<name>` recomputes one retryable section, so a client can retry it without refetching
        the whole dashboard. Not cached: the client asks for it after a failure and expects a fresh result.
        A builder failure is a 200 with `{ "error": ... }` in place of the section, as in the full payload.
        """
        if name not in summary.RETRYABLE_SECTIONS:
            return Response({"error": f"Section '{name}' cannot be requested on its own."}, status=400)
        roles, _builder = summary.RETRYABLE_SECTIONS[name]
        if not summary.user_can_see(user, roles):
            return Response({"error": f"Your role does not include the '{name}' section."}, status=403)
        body = {
            "meta": summary.build_meta(scope, cached=False, generated_at=timezone.now()),
            **summary.build_section_on_its_own(name, scope),
        }
        return Response(body)

    @staticmethod
    def _scope(params) -> summary.DashboardScope:
        company = None
        raw_company = params.get("company_id")
        if raw_company not in (None, ""):
            try:
                company_id = int(raw_company)
            except ValueError:
                raise ValueError("company_id must be an integer.")
            company = CompanyModel.objects.filter(pk=company_id).first()
            if company is None:
                raise ValueError("Unknown company_id.")

        date_from = _optional_date(params.get("date_from"), "date_from")
        date_to = _optional_date(params.get("date_to"), "date_to")
        if date_from and date_to and date_from > date_to:
            raise ValueError("date_from must be on or before date_to.")

        return summary.DashboardScope(
            as_of=summary.as_of_today(),
            company=company,
            date_from=date_from,
            date_to=date_to,
        )
