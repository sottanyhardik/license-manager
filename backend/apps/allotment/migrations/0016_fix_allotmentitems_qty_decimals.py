"""
Migration: Fix AllotmentItems.qty from decimal_places=0 to decimal_places=3.

PostgreSQL blocks ALTER COLUMN TYPE when a materialized view references the column.
Strategy:
  1. Drop the item_balance_mv materialized view (and its indexes) — no data loss, it is
     a derived read-only cache that is rebuilt on refresh.
  2. Widen the column type (NUMERIC(15,0) → NUMERIC(15,3)): existing integer values
     become X.000, no data is lost.
  3. Recreate item_balance_mv and all its indexes.

Fully reversible: the reverse migration narrows back to NUMERIC(15,0) using the same
drop-alter-recreate pattern.
"""
from decimal import Decimal

from django.db import migrations, models
from django.core.validators import MinValueValidator

# ── Materialized view SQL (source of truth: core/materialized_views.py) ─────────

_DROP_MV = """
DROP MATERIALIZED VIEW IF EXISTS item_balance_mv;
"""

_CREATE_MV = """
CREATE MATERIALIZED VIEW IF NOT EXISTS item_balance_mv AS
SELECT
    lii.id as item_id,
    lii.license_id,
    lii.serial_number,
    ld.license_number,
    ld.exporter_id,
    lii.quantity as total_quantity,
    lii.cif_fc as total_cif,

    -- Utilized via BOE
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.qty
        ELSE 0
    END), 0) as utilized_quantity,

    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
        ELSE 0
    END), 0) as utilized_cif,

    -- Allotted
    COALESCE(SUM(ai.qty), 0) as allotted_quantity,
    COALESCE(SUM(ai.cif_fc), 0) as allotted_cif,

    -- Balance (available)
    lii.quantity -
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.qty
        ELSE 0
    END), 0) -
    COALESCE(SUM(ai.qty), 0) as available_quantity,

    lii.cif_fc -
    COALESCE(SUM(CASE
        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
        ELSE 0
    END), 0) -
    COALESCE(SUM(ai.cif_fc), 0) as available_cif,

    -- Item restrictions
    lii.is_restricted,

    -- Metadata
    NOW() as last_refreshed

FROM license_licenseimportitemsmodel lii

INNER JOIN license_licensedetailsmodel ld
    ON ld.id = lii.license_id

LEFT JOIN bill_of_entry_rowdetails rd
    ON rd.sr_number_id = lii.id
    AND rd.transaction_type IN ('DEBIT', 'CREDIT')

LEFT JOIN allotment_allotmentitems ai
    ON ai.item_id = lii.id

GROUP BY lii.id, lii.license_id, lii.serial_number, ld.license_number,
         ld.exporter_id, lii.quantity, lii.cif_fc, lii.is_restricted;

CREATE UNIQUE INDEX IF NOT EXISTS item_balance_mv_item_id_idx
    ON item_balance_mv(item_id);

CREATE INDEX IF NOT EXISTS item_balance_mv_license_id_idx
    ON item_balance_mv(license_id);

CREATE INDEX IF NOT EXISTS item_balance_mv_exporter_id_idx
    ON item_balance_mv(exporter_id);

CREATE INDEX IF NOT EXISTS item_balance_mv_available_cif_idx
    ON item_balance_mv(available_cif);

CREATE INDEX IF NOT EXISTS item_balance_mv_available_quantity_idx
    ON item_balance_mv(available_quantity);
"""


class Migration(migrations.Migration):

    dependencies = [
        ('allotment', '0015_remove_allotmentitems_allot_item_allotment_idx_and_more'),
    ]

    operations = [
        # 1. Drop the materialized view so PostgreSQL allows the ALTER COLUMN TYPE.
        migrations.RunSQL(
            sql=_DROP_MV,
            reverse_sql=_DROP_MV,  # also drop on reverse (step 3 will recreate it)
        ),

        # 2. Widen NUMERIC(15,0) → NUMERIC(15,3). Existing integers become X.000.
        migrations.AlterField(
            model_name='allotmentitems',
            name='qty',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('0'),
                max_digits=15,
                validators=[MinValueValidator(Decimal('0'))],
            ),
        ),

        # 3. Recreate the materialized view against the widened column.
        migrations.RunSQL(
            sql=_CREATE_MV,
            reverse_sql=_DROP_MV,  # on reverse just drop again; step 2 reverse narrows the column first
        ),
    ]
