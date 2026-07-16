"""
Push already-saved local ownership state to a remote server without re-fetching DGFT.

Use when local DB is up-to-date (e.g. update_license_ownership succeeded locally)
but the remote sync failed mid-run (server briefly on old code, network blip, etc.).
"""
from datetime import date as date_cls
from urllib.parse import urlparse

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch

from apps.license.models import LicenseDetailsModel, LicenseOwnership, LicenseTransferModel
from apps.license.management.commands.update_license_ownership import (
    BATCH_SIZE,
    SERVER_BASE_URL,
    authenticate,
    bulk_sync_to_server,
)


def _parse_license_numbers(raw_value):
    if raw_value is None:
        return None

    license_numbers = []
    seen = set()
    for value in raw_value.split(","):
        license_number = value.strip()
        if license_number and license_number not in seen:
            seen.add(license_number)
            license_numbers.append(license_number)

    if not license_numbers:
        raise CommandError("--licenses must contain at least one non-blank license number.")
    return license_numbers


def _parse_since_date(raw_value):
    if raw_value is None:
        return date_cls.today()

    value = raw_value.strip()
    if not value:
        raise CommandError("--since must not be blank.")

    try:
        return date_cls.fromisoformat(value)
    except ValueError as exc:
        raise CommandError("--since must be an ISO date in YYYY-MM-DD format.") from exc


def _validate_positive_int(value, option_name):
    if value is not None and value < 1:
        raise CommandError(f"{option_name} must be greater than zero.")


def _normalize_server_url(server_url):
    value = (server_url or "").strip().rstrip("/")
    if not value:
        raise CommandError("--server must not be blank.")

    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise CommandError("--server must be an absolute http(s) URL.")
    return value


def _iter_license_batches(queryset, batch_size):
    batch = []
    for license_obj in queryset.iterator(chunk_size=batch_size):
        batch.append(license_obj)
        if len(batch) == batch_size:
            yield batch
            batch = []
    if batch:
        yield batch


def _build_payload_from_local(lic):
    try:
        ownership = lic.ownership
    except LicenseOwnership.DoesNotExist:
        ownership = None

    current_owner = None
    if ownership and ownership.current_owner_id:
        co = ownership.current_owner
        current_owner = {"iec": co.iec, "name": co.name}

    if "transfers" in getattr(lic, "_prefetched_objects_cache", {}):
        transfers_qs = lic.transfers.all()
    else:
        transfers_qs = (
            LicenseTransferModel.objects.filter(license=lic)
            .select_related("from_company", "to_company")
            .order_by("transfer_initiation_date")
        )
    transfers = [
        {
            "from_iec": t.from_company.iec if t.from_company else None,
            "to_iec": t.to_company.iec if t.to_company else None,
            "transfer_status": t.transfer_status,
            "transfer_initiation_date": t.transfer_initiation_date.isoformat() if t.transfer_initiation_date else None,
            "transfer_date": t.transfer_date.isoformat() if t.transfer_date else None,
            "transfer_acceptance_date": t.transfer_acceptance_date.isoformat() if t.transfer_acceptance_date else None,
            "cbic_status": t.cbic_status,
            "cbic_response_date": t.cbic_response_date.isoformat() if t.cbic_response_date else None,
            "user_id_transfer_initiation": t.user_id_transfer_initiation,
            "user_id_acceptance": t.user_id_acceptance,
            "from_iec_entity_name": t.from_company.name if t.from_company else None,
            "to_iec_entity_name": t.to_company.name if t.to_company else None,
        }
        for t in transfers_qs
    ]

    return {
        "license_number": lic.license_number,
        "license_date": lic.license_date.strftime("%Y-%m-%d") if lic.license_date else None,
        "exporter_iec": lic.exporter.iec if lic.exporter else None,
        "validity": lic.license_expiry_date.strftime("%d/%m/%Y") if lic.license_expiry_date else None,
        "last_ownership_fetch": ownership.last_ownership_fetch.isoformat() if (ownership and ownership.last_ownership_fetch) else None,
        "file_transfer_status": ownership.file_transfer_status if ownership else None,
        "current_owner": current_owner,
        "transfers": transfers,
    }


class Command(BaseCommand):
    help = "Push already-fetched local ownership data to a remote server (no DGFT fetch)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--server",
            type=str,
            default=None,
            help="Target server URL. Defaults to SERVER_BASE_URL env or https://license-manager.duckdns.org.",
        )
        parser.add_argument(
            "--licenses",
            type=str,
            default=None,
            help="Comma-separated specific license numbers to push.",
        )
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help="ISO date (YYYY-MM-DD). Push licenses with last_ownership_fetch on/after this date. Default: today.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Max number of licenses to push.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=BATCH_SIZE,
            help=f"Batch size for bulk POST (default: {BATCH_SIZE}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Build payloads and report counts without authenticating or POSTing.",
        )

    def handle(self, *args, **options):
        server_url = _normalize_server_url(options["server"] or SERVER_BASE_URL)
        license_numbers = _parse_license_numbers(options["licenses"])
        limit = options["limit"]
        batch_size = options["batch_size"]
        dry_run = options["dry_run"]

        _validate_positive_int(limit, "--limit")
        _validate_positive_int(batch_size, "--batch-size")

        if license_numbers:
            qs = LicenseDetailsModel.objects.filter(license_number__in=license_numbers)
            scope_desc = f"licenses {', '.join(license_numbers)}"
        else:
            since_date = _parse_since_date(options["since"])
            qs = LicenseDetailsModel.objects.filter(
                ownership__last_ownership_fetch__date__gte=since_date,
            )
            scope_desc = f"last_ownership_fetch >= {since_date.isoformat()}"

        transfer_qs = (
            LicenseTransferModel.objects.select_related("from_company", "to_company")
            .order_by("transfer_initiation_date", "id")
        )
        qs = (
            qs.select_related("exporter", "ownership__current_owner")
            .prefetch_related(Prefetch("transfers", queryset=transfer_qs))
            .order_by("id")
        )
        if limit:
            qs = qs[:limit]

        total = qs.count()

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(f"📤 Resync to {server_url}")
        self.stdout.write(f"   scope: {scope_desc}")
        self.stdout.write(f"   total: {total}  batch_size: {batch_size}  dry_run: {dry_run}")
        self.stdout.write("=" * 70)

        if total == 0:
            self.stdout.write("Nothing to push. Exiting.")
            return

        if dry_run:
            for lic in qs[:5]:
                self.stdout.write(f"  would push: id={lic.id} number={lic.license_number}")
            if total > 5:
                self.stdout.write(f"  ... and {total - 5} more")
            return

        self.stdout.write("🔐 Authenticating with server...")
        ok, resolved_url = authenticate(server_url)
        if not ok:
            raise CommandError(f"Auth failed for {server_url}")
        server_url = resolved_url

        total_synced = 0
        total_failed = 0
        all_errors = []

        total_batches = (total + batch_size - 1) // batch_size
        for batch_index, batch in enumerate(_iter_license_batches(qs, batch_size), start=1):
            self.stdout.write(f"\nBatch {batch_index}/{total_batches} — building {len(batch)} payloads...")

            payloads = [_build_payload_from_local(lic) for lic in batch]
            result = bulk_sync_to_server(payloads, server_url) or {}
            if not isinstance(result, dict):
                raise CommandError("Remote sync returned an invalid response.")

            try:
                s = int(result.get("success") or 0)
                f = int(result.get("failed") or 0)
            except (TypeError, ValueError) as exc:
                raise CommandError("Remote sync returned non-numeric counters.") from exc
            total_synced += s
            total_failed += f

            self.stdout.write(f"  ✅ success={s}  ❌ failed={f}")
            for err in (result.get("errors") or [])[:3]:
                self.stdout.write(f"    • {err}")
            all_errors.extend(result.get("errors") or [])

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(
            self.style.SUCCESS(f"Done. Synced {total_synced}/{total}, failed {total_failed}")
        )
        if all_errors:
            self.stdout.write("\nFirst 10 errors:")
            for err in all_errors[:10]:
                self.stdout.write(f"  • {err}")
        if total_failed:
            raise CommandError(f"Remote sync failed for {total_failed} license(s).")
