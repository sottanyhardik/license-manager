"""
Standardized export filename convention — Phase 2A of the export-consistency
initiative.

Existing report exports build `Content-Disposition` filenames ad hoc and
inconsistently — some bake in a filter value (`active_licenses_{days}_days.xlsx`),
some are entirely static with no date at all
(`license_purchase_profit_report.xlsx`). `build_export_filename` gives every
report the same pattern: `<report-slug>_<date-or-range>.<ext>`, using an
ISO date (sorts correctly, unambiguous) rather than the DD-MM-YYYY strings
used elsewhere in this codebase's older, out-of-scope exporters.
"""
from django.utils import timezone


def build_export_filename(report_slug: str, ext: str, *, from_date=None, to_date=None) -> str:
    """Build a standardized export filename: `<report_slug>_<date(s)>.<ext>`.

    - Both `from_date` and `to_date` given and equal: one date.
    - Both given and different: `<from>_to_<to>`.
    - Neither given: today's date (the report has no date-range filter).

    `from_date`/`to_date` may be `date`/`datetime` objects or ISO strings.
    """
    def _iso(value) -> str:
        if isinstance(value, str):
            return value
        return value.isoformat()

    if from_date and to_date:
        from_iso, to_iso = _iso(from_date), _iso(to_date)
        stamp = from_iso if from_iso == to_iso else f"{from_iso}_to_{to_iso}"
    elif from_date:
        stamp = _iso(from_date)
    else:
        stamp = timezone.localdate().isoformat()

    return f"{report_slug}_{stamp}.{ext}"
