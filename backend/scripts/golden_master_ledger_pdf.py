#!/usr/bin/env python
"""Golden-master for the ledger PDF export endpoints.

    export/all?detailed=false     -> _generate_all_licenses_pdf
    export/all?detailed=true      -> _generate_detailed_licenses_pdf (+ _get_license_transactions)
    company-ledger/export?company -> _generate_company_ledger_pdf

Guards the extraction of those generators from views/ledger.py into
services/exporters/. Fingerprints the extracted PDF text (hash) so the output is
proven identical. The Content-Disposition filename embeds datetime.now(), so it
is normalized (timestamp stripped) before comparison.

Usage (backend/, venv):
    python scripts/golden_master_ledger_pdf.py record
    python scripts/golden_master_ledger_pdf.py check
Read-only against the dev DB.
"""
import os
import re
import sys
import io
import json
import hashlib
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django  # noqa: E402
django.setup()  # noqa: E402

from django.conf import settings as _settings  # noqa: E402
for _h in ("testserver", "localhost"):
    if _h not in _settings.ALLOWED_HOSTS:
        _settings.ALLOWED_HOSTS.append(_h)

from django.contrib.auth import get_user_model  # noqa: E402
from rest_framework.test import APIRequestFactory, force_authenticate  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from apps.license.views.ledger import LicenseLedgerViewSet  # noqa: E402
from apps.core.models import CompanyModel  # noqa: E402

BASELINE = os.path.join(os.path.dirname(__file__), ".golden_master", "ledger_pdf.json")
_TS = re.compile(r"_\d{8}_\d{6}")  # the datetime.now() stamp in filenames


def _user():
    return get_user_model().objects.filter(is_superuser=True).first()


def _fingerprint(resp):
    fp = {
        "status": resp.status_code,
        "content_type": resp.get("Content-Type"),
        # normalize the volatile datetime stamp out of the filename
        "content_disposition": _TS.sub("_TS", resp.get("Content-Disposition") or ""),
    }
    if hasattr(resp, "render") and not getattr(resp, "is_rendered", True):
        resp.render()
    content = b"".join(resp.streaming_content) if getattr(resp, "streaming", False) else resp.content
    if resp.status_code != 200:
        fp["body"] = content[:1000].decode("utf-8", "replace")
        return fp
    try:
        reader = PdfReader(io.BytesIO(content))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        # Strip the generation time-of-day (varies second-to-second between runs);
        # financial figures don't contain ':' so they're preserved.
        text = re.sub(r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:[AaPp][Mm])?", "TIME", text)
        fp["n_pages"] = len(reader.pages)
        fp["text_sha256"] = hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()
    except Exception:
        fp["parse_error"] = traceback.format_exc()
    return fp


def snapshot():
    user = _user()
    factory = APIRequestFactory()
    company = CompanyModel.objects.first()
    out = {}

    for label, action, qs in [
        ("export_all_plain", "export_all", "detailed=false"),
        ("export_all_detailed", "export_all", "detailed=true"),
        ("company_ledger_export", "company_ledger_export", f"company={company.id if company else 0}"),
    ]:
        view = LicenseLedgerViewSet.as_view({"get": action})
        req = factory.get(f"/api/license-ledger/x/?{qs}")
        force_authenticate(req, user=user)
        try:
            out[label] = _fingerprint(view(req))
        except Exception:
            out[label] = {"invoke_error": traceback.format_exc()}
    return out


def _diff(a, b, path=""):
    if isinstance(a, dict):
        for k in a.keys() | b.keys():
            if k not in a:
                yield f"{path}.{k}: added"
            elif k not in b:
                yield f"{path}.{k}: removed"
            else:
                yield from _diff(a[k], b[k], f"{path}.{k}")
    elif a != b:
        yield f"{path}: {a!r} -> {b!r}"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    snap = snapshot()
    if mode == "record":
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        json.dump(snap, open(BASELINE, "w"), indent=2, sort_keys=True)
        for k, v in snap.items():
            print(f"  {k}: status={v.get('status')} pages={v.get('n_pages')} sha={ (v.get('text_sha256') or '')[:12] }")
        print(f"[ledger-gm] baseline -> {BASELINE}")
        return
    if mode != "check":
        print(__doc__)
        raise SystemExit(2)
    base = json.load(open(BASELINE))
    diffs = list(_diff(base, snap))
    if not diffs:
        print("[ledger-gm] PASS — ledger PDF output identical to baseline.")
        return
    print(f"[ledger-gm] FAIL — {len(diffs)} diff(s):")
    for d in diffs[:40]:
        print("   ", d)
    raise SystemExit(1)


if __name__ == "__main__":
    main()
