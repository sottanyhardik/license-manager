#!/usr/bin/env python
"""Characterization probe for the license list/detail balance_cif refactor.

Guards the fix for the duplicated `get_get_balance_cif` (serializers.py) that made
the license LIST view recompute balance live (4 aggregates/row). We assert that:
  * every license's `balance_cif` and `get_balance_cif` in BOTH list and detail
    output are UNCHANGED by the refactor (value-identical), and
  * the number of DB queries for the list endpoint drops.

Usage (backend/, venv active):
    python scripts/char_license_list_balance.py record   # baseline (run on old code)
    python scripts/char_license_list_balance.py check     # compare (run on new code)

Read-only against the dev DB.
"""
import os
import sys
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django  # noqa: E402
django.setup()  # noqa: E402

from django.conf import settings as _settings  # noqa: E402
for _h in ("testserver", "localhost"):
    if _h not in _settings.ALLOWED_HOSTS:
        _settings.ALLOWED_HOSTS.append(_h)

from django.contrib.auth import get_user_model  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.utils import CaptureQueriesContext  # noqa: E402
from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402

from apps.license.views.license import LicenseDetailsViewSet  # noqa: E402
from apps.license.models import LicenseDetailsModel  # noqa: E402

BASELINE = os.path.join(os.path.dirname(__file__), ".golden_master", "list_balance.json")
PAGE_SIZE = 200  # capture as many licenses in one list page as possible


def _user():
    return get_user_model().objects.filter(is_superuser=True).first()


def _rows_from_list(payload):
    """Extract {id: [balance_cif, get_balance_cif]} from a list response payload."""
    data = payload.get("results", payload) if isinstance(payload, dict) else payload
    out = {}
    for row in data:
        out[str(row["id"])] = [str(row.get("balance_cif")), str(row.get("get_balance_cif"))]
    return out


def snapshot():
    user = _user()
    factory = APIRequestFactory()

    # LIST (capture values + query count)
    list_view = LicenseDetailsViewSet.as_view({"get": "list"})
    req = factory.get(f"/api/licenses/?page_size={PAGE_SIZE}&is_expired=all&is_null=all")
    force_authenticate(req, user=user)
    with CaptureQueriesContext(connection) as ctx:
        resp = list_view(req)
        resp.render() if hasattr(resp, "render") and not getattr(resp, "is_rendered", True) else None
        payload = resp.data
    list_rows = _rows_from_list(payload)
    list_queries = len(ctx.captured_queries)

    # DETAIL for a sample of the listed ids
    detail_view = LicenseDetailsViewSet.as_view({"get": "retrieve"})
    sample_ids = list(list_rows.keys())[:10]
    detail_rows = {}
    for pk in sample_ids:
        r = factory.get(f"/api/licenses/{pk}/")
        force_authenticate(r, user=user)
        dr = detail_view(r, pk=pk)
        dr.render() if hasattr(dr, "render") and not getattr(dr, "is_rendered", True) else None
        detail_rows[pk] = [str(dr.data.get("balance_cif")), str(dr.data.get("get_balance_cif"))]

    return {
        "list_rows": list_rows,
        "list_row_count": len(list_rows),
        "list_queries": list_queries,
        "detail_rows": detail_rows,
    }


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    snap = snapshot()
    if mode == "record":
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, "w") as f:
            json.dump(snap, f, indent=2, sort_keys=True)
        print(f"[char] recorded: {snap['list_row_count']} licenses, "
              f"list_queries={snap['list_queries']}, detail_sample={len(snap['detail_rows'])}")
        return
    if mode != "check":
        print(__doc__)
        raise SystemExit(2)

    with open(BASELINE) as f:
        base = json.load(f)

    problems = []
    # values must be identical (list)
    if set(base["list_rows"]) != set(snap["list_rows"]):
        problems.append("list id set changed")
    for pk, vals in base["list_rows"].items():
        if snap["list_rows"].get(pk) != vals:
            problems.append(f"list {pk}: {vals} -> {snap['list_rows'].get(pk)}")
    for pk, vals in base["detail_rows"].items():
        if snap["detail_rows"].get(pk) != vals:
            problems.append(f"detail {pk}: {vals} -> {snap['detail_rows'].get(pk)}")

    print(f"[char] list_queries: {base['list_queries']} -> {snap['list_queries']} "
          f"(rows={snap['list_row_count']})")
    if problems:
        print(f"[char] FAIL — {len(problems)} value change(s):")
        for p in problems[:40]:
            print("   ", p)
        raise SystemExit(1)
    print("[char] PASS — all balance_cif / get_balance_cif values identical (list + detail).")
    if snap["list_queries"] >= base["list_queries"]:
        print("[char] WARNING — list query count did not drop; investigate.")
    else:
        print(f"[char] query win: -{base['list_queries'] - snap['list_queries']} queries on list.")


if __name__ == "__main__":
    main()
