from decimal import Decimal

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('bill_of_entry', '0007_rowdetails_is_frozen'),
    ]

    operations = [
        # Drop all materialized views that depend on cif_inr / cif_fc before altering columns.
        # dashboard_stats_mv depends on license_balance_mv, so drop it first.
        migrations.RunSQL(
            sql="""
                DROP MATERIALIZED VIEW IF EXISTS dashboard_stats_mv CASCADE;
                DROP MATERIALIZED VIEW IF EXISTS item_balance_mv CASCADE;
                DROP MATERIALIZED VIEW IF EXISTS license_balance_mv CASCADE;
            """,
            reverse_sql="SELECT 1;",
        ),

        migrations.AlterField(
            model_name='rowdetails',
            name='cif_inr',
            field=models.DecimalField(
                default=Decimal('0'),
                decimal_places=3,
                max_digits=15,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),
        migrations.AlterField(
            model_name='rowdetails',
            name='cif_fc',
            field=models.DecimalField(
                default=Decimal('0'),
                decimal_places=3,
                max_digits=15,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
            ),
        ),

        # Recreate license_balance_mv
        migrations.RunSQL(
            sql="""
                CREATE MATERIALIZED VIEW IF NOT EXISTS license_balance_mv AS
                SELECT
                    ld.id as license_id,
                    ld.license_number,
                    ld.exporter_id,
                    COALESCE((
                        SELECT SUM(lei.cif_fc)
                        FROM license_licenseexportitemmodel lei
                        WHERE lei.license_id = ld.id
                    ), 0) as total_cif,
                    ld.license_date,
                    ld.license_expiry_date,
                    ld.is_active,
                    COALESCE(SUM(CASE
                        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
                        ELSE 0
                    END), 0) as utilized_cif,
                    COALESCE(SUM(CASE
                        WHEN ai.allotment_id IS NOT NULL THEN ai.cif_fc
                        ELSE 0
                    END), 0) as allotted_cif,
                    COALESCE((
                        SELECT SUM(lei.cif_fc)
                        FROM license_licenseexportitemmodel lei
                        WHERE lei.license_id = ld.id
                    ), 0) -
                    COALESCE(SUM(CASE
                        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
                        ELSE 0
                    END), 0) -
                    COALESCE(SUM(CASE
                        WHEN ai.allotment_id IS NOT NULL THEN ai.cif_fc
                        ELSE 0
                    END), 0) as balance_cif,
                    NOW() as last_refreshed
                FROM license_licensedetailsmodel ld
                LEFT JOIN license_licenseimportitemsmodel lii ON lii.license_id = ld.id
                LEFT JOIN bill_of_entry_rowdetails rd
                    ON rd.sr_number_id = lii.id
                    AND rd.transaction_type IN ('DEBIT', 'CREDIT')
                LEFT JOIN allotment_allotmentitems ai ON ai.item_id = lii.id
                GROUP BY ld.id, ld.license_number, ld.exporter_id,
                         ld.license_date, ld.license_expiry_date, ld.is_active;

                CREATE UNIQUE INDEX IF NOT EXISTS license_balance_mv_license_id_idx
                    ON license_balance_mv(license_id);
                CREATE INDEX IF NOT EXISTS license_balance_mv_exporter_id_idx
                    ON license_balance_mv(exporter_id);
                CREATE INDEX IF NOT EXISTS license_balance_mv_balance_cif_idx
                    ON license_balance_mv(balance_cif);
                CREATE INDEX IF NOT EXISTS license_balance_mv_is_active_idx
                    ON license_balance_mv(is_active);
            """,
            reverse_sql="DROP MATERIALIZED VIEW IF EXISTS license_balance_mv CASCADE;",
        ),

        # Recreate item_balance_mv
        migrations.RunSQL(
            sql="""
                CREATE MATERIALIZED VIEW IF NOT EXISTS item_balance_mv AS
                SELECT
                    lii.id as item_id,
                    lii.license_id,
                    lii.serial_number,
                    ld.license_number,
                    ld.exporter_id,
                    lii.quantity as total_quantity,
                    lii.cif_fc as total_cif,
                    COALESCE(SUM(CASE
                        WHEN rd.transaction_type = 'DEBIT' THEN rd.qty
                        ELSE 0
                    END), 0) as utilized_quantity,
                    COALESCE(SUM(CASE
                        WHEN rd.transaction_type = 'DEBIT' THEN rd.cif_inr
                        ELSE 0
                    END), 0) as utilized_cif,
                    COALESCE(SUM(ai.qty), 0) as allotted_quantity,
                    COALESCE(SUM(ai.cif_fc), 0) as allotted_cif,
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
                    lii.is_restricted,
                    NOW() as last_refreshed
                FROM license_licenseimportitemsmodel lii
                INNER JOIN license_licensedetailsmodel ld ON ld.id = lii.license_id
                LEFT JOIN bill_of_entry_rowdetails rd
                    ON rd.sr_number_id = lii.id
                    AND rd.transaction_type IN ('DEBIT', 'CREDIT')
                LEFT JOIN allotment_allotmentitems ai ON ai.item_id = lii.id
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
            """,
            reverse_sql="DROP MATERIALIZED VIEW IF EXISTS item_balance_mv CASCADE;",
        ),

        # Recreate dashboard_stats_mv (depends on license_balance_mv)
        migrations.RunSQL(
            sql="""
                CREATE MATERIALIZED VIEW IF NOT EXISTS dashboard_stats_mv AS
                SELECT
                    (SELECT COUNT(*) FROM license_licensedetailsmodel
                     WHERE is_active = true) as active_licenses_count,
                    (SELECT COUNT(*) FROM license_licensedetailsmodel
                     WHERE is_active = true
                     AND license_expiry_date < CURRENT_DATE) as expired_licenses_count,
                    (SELECT COUNT(*) FROM license_licensedetailsmodel
                     WHERE is_active = true
                     AND license_expiry_date BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '30 days')
                     as expiring_soon_count,
                    (SELECT COALESCE(SUM(total_cif), 0) FROM license_balance_mv
                     WHERE is_active = true) as total_cif_value,
                    (SELECT COALESCE(SUM(balance_cif), 0) FROM license_balance_mv
                     WHERE is_active = true) as available_cif_value,
                    (SELECT COALESCE(SUM(utilized_cif), 0) FROM license_balance_mv
                     WHERE is_active = true) as utilized_cif_value,
                    (SELECT COUNT(*) FROM bill_of_entry_billofentrymodel
                     WHERE bill_of_entry_date >= CURRENT_DATE - INTERVAL '30 days') as boe_last_30_days,
                    (SELECT COUNT(*) FROM allotment_allotmentmodel
                     WHERE created_on >= CURRENT_DATE - INTERVAL '30 days') as allotments_last_30_days,
                    (SELECT COUNT(DISTINCT exporter_id) FROM license_licensedetailsmodel
                     WHERE is_active = true) as active_companies_count,
                    NOW() as last_refreshed;

                CREATE UNIQUE INDEX IF NOT EXISTS dashboard_stats_mv_idx
                    ON dashboard_stats_mv(last_refreshed);
            """,
            reverse_sql="DROP MATERIALIZED VIEW IF EXISTS dashboard_stats_mv CASCADE;",
        ),
    ]
