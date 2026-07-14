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
from decimal import Decimal

# `backend/` (parent of this script's dir) must be on sys.path so the
# `lmanagement` settings package is importable when run as a standalone
# script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django  # noqa: E402

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
django.setup()

from apps.license.models import LicenseDetailsModel  # noqa: E402
from apps.license.services.condition_pool import compute_condition_pools  # noqa: E402
from apps.license.services.e5_plan import (  # noqa: E402
    E5_CATS,
    E5_PLAN_CATS,
    E5_UNIT_PRICES,
    WPC_MAX_PRICE,
    WPC_MIN_PRICE,
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

    # Run the waterfall.
    cond_pools = compute_condition_pools(lic)
    pool_10 = cond_pools.get('10%', Decimal('0'))
    planned, rate = compute_e5_plan(totals, None, balance_cif, pool_10)

    # Replay the deduction sequence so we can print the running balance at
    # each step exactly as the spec describes it.
    print('\n  Waterfall (step-by-step):')
    print(f'    Initial Balance CIF                       = {balance_cif:>12,.2f}')
    remaining = balance_cif
    fixed_steps = ('DIETARY FIBRE', 'SWP', 'PKO', 'RBD', 'OLIVE OIL')
    for step in fixed_steps:
        used = planned[step]
        # For SWP we'll subtract only the *fixed-rate* portion here; the
        # SWP recalc fold comes next so it's a separate line.
        if step == 'SWP':
            fixed_swp = float(E5_UNIT_PRICES['SWP']) * totals['SWP']
            used = min(fixed_swp, remaining) if totals['SWP'] > 0 else 0.0
        remaining -= used
        unit_price = round(used / totals[step], 2) if totals.get(step) else 0.0
        print(f'    {step:<32} qty {totals[step]:>10,.2f} '
              f'× rate {float(E5_UNIT_PRICES[step]):>5.2f} '
              f'→ used {used:>12,.2f}  '
              f'(unit_price {unit_price:>7.2f}, '
              f'remaining {remaining:>12,.2f})')

    # SWP recalc — the difference between `planned['SWP']` (final) and the
    # fixed-rate slice we subtracted above is the recalc amount.
    fixed_swp_used = min(float(E5_UNIT_PRICES['SWP']) * totals['SWP'], balance_cif) \
        if totals['SWP'] > 0 else 0.0
    swp_recalc_extra = planned['SWP'] - fixed_swp_used
    if swp_recalc_extra > 0.0001:
        print(f'    SWP RECALC fold                           '
              f'+= {swp_recalc_extra:>12,.2f}  (new SWP rate {rate["SWP"]:.4f})')
        remaining -= swp_recalc_extra
    else:
        print('    SWP RECALC fold                            (skipped — '
              'no remaining balance or SWP qty = 0)')

    # WPC step (dynamic price).
    if planned['WPC'] > 0:
        print(f'    WPC                              qty {totals["WPC"]:>10,.2f} '
              f'× rate {rate["WPC"]:>5.2f} → used {planned["WPC"]:>12,.2f}')
    else:
        print(f'    WPC                              qty {totals["WPC"]:>10,.2f} '
              f'→ used 0.00  (skipped: no balance or zero qty)')
    remaining -= planned['WPC']
    print(f'                                                                       '
          f'remaining {remaining:>12,.2f}')

    # Wheat-flour mop-up.
    if planned['WHEAT FLOUR'] > 0:
        print(f'    WHEAT FLOUR mop-up               qty {totals["WHEAT FLOUR"]:>10,.2f} '
              f'→ used {planned["WHEAT FLOUR"]:>12,.2f}  '
              f'(dyn unit_price {rate["WHEAT FLOUR"]:.4f})')
        remaining -= planned['WHEAT FLOUR']
    else:
        print(f'    WHEAT FLOUR mop-up               qty {totals["WHEAT FLOUR"]:>10,.2f} '
              f'→ used 0.00  (skipped)')

    print(f'\n    FINAL remaining balance CIF              = {remaining:>12,.2f}')

    # Final dump.
    print('\n  Final planned-CIF per category:')
    print(f'    {"Category":<20}{"Qty":>14}{"Unit Price":>14}{"Planned CIF":>16}')
    total_planned = 0.0
    for cat in E5_CATS:
        q = totals.get(cat, 0)
        pc = planned[cat]
        up = round(pc / q, 2) if q else 0.0
        total_planned += pc
        print(f'    {cat:<20}{q:>14,.2f}{up:>14,.2f}{pc:>16,.2f}')
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
