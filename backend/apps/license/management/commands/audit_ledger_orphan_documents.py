"""Read-only forensic inventory of ledger purchase-document recovery sources.

The command deliberately does not attach files.  Its CSV is suitable for the
readiness review screen and makes the candidate rule reproducible.
"""
from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import FileField

from apps.license.models import LicenseLedgerPackageJob
from apps.license.services.ledger_package_recovery import missing_purchase_trades, normalize_invoice


DATE_RE = re.compile(r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b")
MONEY_RE = re.compile(r"(?:grand\s+total|invoice\s+total|total\s+amount|net\s+amount)\D{0,30}([0-9][0-9,]*\.\d{2})", re.I)
INVOICE_RE = re.compile(r"(?:invoice\s*(?:no|number|#)?|bill\s*(?:no|number|#)?)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]{2,})", re.I)


def _referenced_storage_keys():
    keys = set()
    for model in apps.get_models():
        for field in model._meta.fields:
            if isinstance(field, FileField):
                keys.update(value for value in model.objects.exclude(**{field.name: ""}).exclude(**{field.name: None}).values_list(field.name, flat=True) if value)
    return keys


def _read_evidence(path: Path):
    data = path.read_bytes()
    result = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "kind": "UNKNOWN", "metadata": "", "text": "", "ocr": ""}
    suffix = path.suffix.lower()
    if data.startswith(b"%PDF-"):
        result["kind"] = "PDF"
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            result["metadata"] = str(reader.metadata or {})[:2000]
            result["text"] = "\n".join((page.extract_text() or "") for page in reader.pages)[:20000]
        except Exception as exc:
            result["metadata"] = "PDF_READ_ERROR: " + str(exc)
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        result["kind"] = "IMAGE"
        try:
            from PIL import Image
            image = Image.open(path)
            image.verify()
            try:
                import pytesseract
                result["ocr"] = pytesseract.image_to_string(Image.open(path))[:20000]
            except Exception as exc:
                result["ocr"] = "OCR_UNAVAILABLE: " + str(exc)
        except Exception as exc:
            result["metadata"] = "IMAGE_READ_ERROR: " + str(exc)
    return result


def _fields(text):
    invoices = sorted(set(normalize_invoice(v) for v in INVOICE_RE.findall(text) if v))
    dates = sorted(set(DATE_RE.findall(text)))
    total = MONEY_RE.search(text)
    return invoices, dates, (total.group(1).replace(",", "") if total else "")


class Command(BaseCommand):
    help = "Inventory unreferenced media files and exact-match them to requested missing purchases; never writes DB/storage."

    def add_arguments(self, parser):
        parser.add_argument("--job-key", required=True)
        parser.add_argument("--output", required=True, help="CSV output path (outside media is recommended)")

    def handle(self, *args, **options):
        job = LicenseLedgerPackageJob.objects.filter(key=options["job_key"]).first()
        if not job:
            raise CommandError("Unknown package job key")
        root = Path(settings.MEDIA_ROOT)
        if not root.exists():
            raise CommandError("Configured MEDIA_ROOT does not exist")
        missing = {}
        for item in job.items.select_related("license"):
            for trade in missing_purchase_trades(item.license):
                missing[trade.pk] = trade
        referenced = _referenced_storage_keys()
        # Only documents are candidates; generated packages and non-document
        # assets are excluded.  An unreferenced generated sale PDF is reported
        # but is not eligible to satisfy a supplier-purchase requirement.
        files = [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}]
        rows = []
        for path in files:
            key = path.relative_to(root).as_posix()
            if key in referenced:
                continue
            evidence = _read_evidence(path)
            text = evidence["text"] or evidence["ocr"]
            invoice_numbers, dates, total = _fields(text)
            exact = []
            for trade in missing.values():
                if normalize_invoice(trade.invoice_number) not in invoice_numbers:
                    continue
                # Supplier evidence needs a visible exact name; extraction has
                # no reliable structured supplier field, therefore absence is
                # deliberately non-qualifying.
                supplier = (getattr(trade.from_company, "name", "") or "").casefold()
                supplier_match = bool(supplier and supplier in text.casefold())
                date_match = bool(trade.invoice_date and str(trade.invoice_date) in dates)
                try:
                    amount_match = bool(total and Decimal(total) == trade.total_amount)
                except InvalidOperation:
                    amount_match = False
                if supplier_match and date_match and amount_match:
                    exact.append(trade.pk)
            scope = "PURCHASE_CANDIDATE" if key.startswith("trade/purchase_invoices/") else "NON_PURCHASE_ORPHAN"
            status = "UNIQUE_EXACT_MATCH" if len(exact) == 1 and scope == "PURCHASE_CANDIDATE" else ("AMBIGUOUS_OR_INSUFFICIENT_EVIDENCE" if exact else "NO_DETERMINISTIC_MATCH")
            rows.append({"audit_timestamp": datetime.now(timezone.utc).isoformat(), "source_storage_key": key, "source_checksum": evidence["sha256"], "source_bytes": evidence["bytes"], "source_type": evidence["kind"], "source_scope": scope, "pdf_metadata": evidence["metadata"], "extracted_invoice_numbers": "|".join(invoice_numbers), "extracted_dates": "|".join(dates), "extracted_total": total, "extracted_text_excerpt": text.replace("\n", " ")[:1000], "candidate_trade_ids": "|".join(map(str, exact)), "matching_rule": "EXACT_NORMALIZED_INVOICE_AND_VISIBLE_SUPPLIER_AND_EXACT_DATE_AND_EXACT_TOTAL", "status": status})
        destination = Path(options["output"])
        destination.parent.mkdir(parents=True, exist_ok=True)
        columns = list(rows[0]) if rows else ["audit_timestamp", "source_storage_key", "source_checksum", "source_bytes", "source_type", "source_scope", "pdf_metadata", "extracted_invoice_numbers", "extracted_dates", "extracted_total", "extracted_text_excerpt", "candidate_trade_ids", "matching_rule", "status"]
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader(); writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS("wrote %s unreferenced document rows; %s requested missing purchases; %s unique exact matches" % (len(rows), len(missing), sum(r["status"] == "UNIQUE_EXACT_MATCH" for r in rows))))
