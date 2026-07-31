"""Standalone verifier for the E5 utilization-planning waterfall.

Usage:
    cd backend && ../.venv/bin/python scripts/verify_e5_plan.py 0311052707 0311054202

Replays the classifier + compute_e5_plan exactly as views/license.py does,
prints aggregated quantities per category, every step of the waterfall, and
the final balance.
"""
import os
import sys
from collections import defaultdict

# `backend/` (parent of this script's dir) must be on sys.path so the
# `lmanagement` settings package is importable when run as a standalone
# script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel  # noqa: E402
from apps.license.services.e5_plan import (  # noqa: E402
    E5_CATS,
    E5_PLAN_CATS,
    classify_e5_item,
    compute_e5_plan,
)


def build_bal_agg(license_obj):
    """Mirror the `_bal_agg` aggregation in views/license.py:951-962."""
    agg = defaultdict(lambda: {
        'qty': 0.0,
        'total_qty': 0.0,
        'sr_ids': [],
        'description': '',
        'hs_code': '',
        'condition_type': '',
    })
    for item in license_obj.import_license.all():
        key = (
            ', '.join(sorted([i.name for i in item.items.all()]))
            if item.items.exists()
            else (item.description or '-')
        )
        agg[key]['qty'] += float(item.available_quantity or 0)
        agg[key]['total_qty'] += float(item.quantity or 0)
        agg[key]['sr_ids'].append(item.serial_number)
        if not agg[key]['description']:
            agg[key]['description'] = item.description or key
        if not agg[key]['hs_code']:
            agg[key]['hs_code'] = str(item.hs_code.hs_code if item.hs_code else '-')
        if item.condition_type and not agg[key]['condition_type']:
            agg[key]['condition_type'] = item.condition_type
    return agg


def verify(license_number: str):
    print('=' * 78)
    print(f'LICENCE  {license_number}')
    print('=' * 78)

    lic = LicenseDetailsModel.objects.get(license_number=license_number)
    balance_cif = float(lic.balance_cif or 0)
    norm_classes = list(lic.export_license.values_list('norm_class__norm_class', flat=True))
    is_e5 = any(n and str(n).strip() == 'E5' for n in norm_classes)
    print(f'  id={lic.id}')
    print(f'  norm classes = {norm_classes}')
    print(f'  is_e5        = {is_e5}')
    print(f'  balance_cif  = {balance_cif:,.2f}')

    bal_agg = build_bal_agg(lic)

    # Classification pass — exactly as views/license.py does.
    totals = {c: 0.0 for c in E5_PLAN_CATS}
    first_desc = {}
    unclassified = []
    for ik in bal_agg:
        bq = bal_agg[ik]['qty']
        hs = bal_agg[ik]['hs_code'] or ''
        de = bal_agg[ik]['description'] or ik
        cat = classify_e5_item(ik, hs, de)
        if cat:
            totals[cat] += bq
            if not first_desc.get(cat):
                first_desc[cat] = de
        else:
            unclassified.append((ik, hs, de, bq))

    print('\n  Raw import items (bal_agg) by item key:')
    print(f'    {"Item":<45}{"HSN":<14}{"Bal Qty":>14}')
    for ik in sorted(bal_agg.keys()):
        a = bal_agg[ik]
        print(f'    {ik[:45]:<45}{(a["hs_code"] or "-"):<14}{a["qty"]:>14,.2f}')

    print('\n  Aggregated category totals:')
    for cat in E5_CATS:
        print(f'    {cat:<20} qty = {totals.get(cat, 0):>14,.2f}   (desc: {first_desc.get(cat, "-")})')
    if unclassified:
        print('\n  Unclassified items (NOT used by the planner):')
        for ik, hs, de, bq in unclassified:
            print(f'    {ik[:40]:<40} HSN={hs:<12} qty={bq:>10,.2f}  desc={de}')

    # Run the waterfall. `pool_10pct` is accepted by compute_e5_plan for
    # legacy signature compatibility but no longer consumed.
    planned, rate = compute_e5_plan(totals, None, balance_cif)

    # Informational only — mirrors the Special Validation predicate in
    # `compute_e5_plan` so the report shows whether it would have fired,
    # without re-implementing the actual allocation math here.
    milk_total = totals.get('MILK PRODUCTS', 0.0) + totals.get('EGG ALBUMIN / WPC', 0.0)
    special_triggered = milk_total > 0 and 0 < balance_cif < milk_total * 1.5
    print('\n  Special Validation:')
    print(f'    milk_total_qty = {milk_total:>12,.2f}   threshold (×1.50) = {milk_total * 1.5:>12,.2f}')
    print(f'    triggered      = {special_triggered}  (balance_cif = {balance_cif:,.2f})')

    # Final dump — every category compute_e5_plan returns, plus the DWP/SWP
    # sub-step breakdown (DWP/SWP/WPC rates all live on MILK_CONFIG_E5).
    print('\n  Final planned-CIF per category:')
    print(f'    {"Category":<20}{"Qty":>14}{"Unit Price":>14}{"Planned CIF":>16}')
    total_planned = 0.0
    for cat in E5_CATS:
        q = totals.get(cat, 0)
        pc = planned[cat]
        up = round(pc / q, 2) if q else 0.0
        total_planned += pc
        print(f'    {cat:<20}{q:>14,.2f}{up:>14,.2f}{pc:>16,.2f}')
    print('    ── milk sub-steps (DWP / SWP; WPC is folded into EGG ALBUMIN / WPC above) ──')
    for step in ('DWP', 'SWP'):
        print(f'    {step:<20}{"":>14}{rate[step]:>14,.2f}{planned[step]:>16,.2f}')
    print(f'    {"TOTAL PLANNED":<20}{"":>14}{"":>14}{total_planned:>16,.2f}')
    print(f'    {"FINAL BALANCE":<20}{"":>14}{"":>14}{(balance_cif - total_planned):>16,.2f}')


if __name__ == '__main__':
    license_numbers = sys.argv[1:] or ['0311052707', '0311054202']
    for ln in license_numbers:
        try:
            verify(ln)
        except LicenseDetailsModel.DoesNotExist:
            print(f'License {ln}: NOT FOUND')
        print()
