"""Tests for reconcile_incentive_license_status: dry run, backup, idempotency, safety."""
import csv
import json
from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from apps.core.models import CompanyModel, PortModel
from apps.license.models import IncentiveLicense
from apps.trade.models import IncentiveTradeLine, LicenseTrade

_SEQ = iter(range(1, 10_000_000))


def _n():
    return next(_SEQ)


@pytest.fixture
def parties(db):
    n = _n()
    return {
        "exporter": CompanyModel.objects.create(iec=f"5{n:09d}", name=f"Exp {n}"),
        "buyer": CompanyModel.objects.create(iec=f"4{n:09d}", name=f"Buy {n}"),
        "port": PortModel.objects.create(code=f"Q{n:05d}", name=f"Port {n}"),
    }


def _licence(parties, value="1000.00", number=None):
    n = _n()
    return IncentiveLicense.objects.create(
        license_type="RODTEP",
        license_number=number or f"RCN{n:08d}",
        license_date=date(2025, 12, 19),
        exporter=parties["exporter"],
        port_code=parties["port"],
        license_value=Decimal(value),
        is_active=True,
    )


def _sale_line(parties, licence, value):
    n = _n()
    trade = LicenseTrade.objects.create(
        from_company=parties["exporter"], to_company=parties["buyer"], direction="SALE",
        invoice_number=f"RCN-SALE-{n}", invoice_date=date(2025, 12, 23), license_type="INCENTIVE",
    )
    IncentiveTradeLine.objects.bulk_create([
        IncentiveTradeLine(
            trade=trade, incentive_license=licence, license_value=Decimal(value),
            rate_pct=Decimal("97.25"), amount_inr=Decimal(value),
        )
    ])


def _stored(licence):
    licence.refresh_from_db()
    return licence.sold_value, licence.balance_value, licence.sold_status


def _csv_rows(report_dir):
    files = sorted(report_dir.glob("incentive_status_reconciliation_*.csv"))
    assert files, "command must always write a CSV report"
    with files[-1].open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


@pytest.mark.django_db
def test_dry_run_changes_nothing_and_reports_correctable_row(parties, tmp_path):
    lic = _licence(parties, "1000.00")
    _sale_line(parties, lic, "1000.00")
    IncentiveLicense.objects.filter(pk=lic.pk).update(
        sold_value=Decimal("0.00"), balance_value=Decimal("0.00"), sold_status="NO",
    )  # stale cache

    out = StringIO()
    call_command("reconcile_incentive_license_status", "--report-dir", str(tmp_path), stdout=out)

    assert _stored(lic) == (Decimal("0.00"), Decimal("0.00"), "NO")  # untouched
    row = next(r for r in _csv_rows(tmp_path) if r["licence_number"] == lic.license_number)
    assert row["category"] == "CORRECTABLE"
    assert "Dry run" in out.getvalue()


@pytest.mark.django_db
def test_apply_writes_backup_then_corrects_and_second_run_is_noop(parties, tmp_path):
    lic = _licence(parties, "1000.00")
    _sale_line(parties, lic, "1000.00")
    IncentiveLicense.objects.filter(pk=lic.pk).update(
        sold_value=Decimal("0.00"), balance_value=Decimal("0.00"), sold_status="NO",
    )

    call_command("reconcile_incentive_license_status", "--apply", "--licence", lic.license_number,
                 "--report-dir", str(tmp_path), stdout=StringIO())

    assert _stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")
    backups = list(tmp_path.glob("incentive_status_backup_*.json"))
    assert len(backups) == 1
    entry = json.loads(backups[0].read_text())[0]
    assert entry["licence_number"] == lic.license_number
    assert entry["before"] == {"sold_value": "0.00", "balance_value": "0.00", "sold_status": "NO"}
    assert entry["after"] == {"sold_value": "1000.00", "balance_value": "0.00", "sold_status": "YES"}

    second = StringIO()
    call_command("reconcile_incentive_license_status", "--apply", "--licence", lic.license_number,
                 "--report-dir", str(tmp_path), stdout=second)

    assert "Applied 0 correction(s)." in second.getvalue()
    assert _stored(lic) == (Decimal("1000.00"), Decimal("0.00"), "YES")


@pytest.mark.django_db
def test_no_sale_evidence_row_is_never_zeroed_by_apply(parties, tmp_path):
    lic = _licence(parties, "2000.00")
    IncentiveLicense.objects.filter(pk=lic.pk).update(
        sold_value=Decimal("1500.00"), balance_value=Decimal("500.00"), sold_status="YES",
    )  # cache claims a sale that no trade line supports

    call_command("reconcile_incentive_license_status", "--apply", "--licence", lic.license_number,
                 "--report-dir", str(tmp_path), stdout=StringIO())

    assert _stored(lic) == (Decimal("1500.00"), Decimal("500.00"), "YES")  # manual review, untouched
    row = next(r for r in _csv_rows(tmp_path) if r["licence_number"] == lic.license_number)
    assert row["category"] == "NO_SALE_EVIDENCE"
    assert row["proposed_action"] == "manual review"


@pytest.mark.django_db
def test_oversold_row_is_reported_for_review_and_not_clamped(parties, tmp_path):
    lic = _licence(parties, "1000.00")
    trade = LicenseTrade.objects.create(
        from_company=parties["exporter"], to_company=parties["buyer"], direction="SALE",
        invoice_number=f"RCN-OVER-{_n()}", invoice_date=date(2025, 12, 23), license_type="INCENTIVE",
    )
    # Normal create (not bulk) so the signal keeps the cache consistent.
    IncentiveTradeLine.objects.create(
        trade=trade, incentive_license=lic, license_value=Decimal("1150.00"),
        rate_pct=Decimal("97.25"), amount_inr=Decimal("1150.00"),
    )

    call_command("reconcile_incentive_license_status", "--apply", "--licence", lic.license_number,
                 "--report-dir", str(tmp_path), stdout=StringIO())

    assert _stored(lic) == (Decimal("1150.00"), Decimal("-150.00"), "YES")
    row = next(r for r in _csv_rows(tmp_path) if r["licence_number"] == lic.license_number)
    assert row["category"] == "OVERSOLD"
