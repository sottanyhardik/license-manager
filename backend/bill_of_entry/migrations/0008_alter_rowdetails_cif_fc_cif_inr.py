from decimal import Decimal

from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('bill_of_entry', '0007_rowdetails_is_frozen'),
    ]

    operations = [
        # Drop materialized view and its indexes before altering columns it depends on
        migrations.RunSQL(
            sql="""
                DROP MATERIALIZED VIEW IF EXISTS license_balance_mv CASCADE;
            """,
            reverse_sql="""
                -- recreated at the end of this migration
            """,
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

        # Recreate the materialized view after column type changes
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
                LEFT JOIN license_licenseimportitemsmodel lii
                    ON lii.license_id = ld.id
                LEFT JOIN bill_of_entry_rowdetails rd
                    ON rd.sr_number_id = lii.id
                    AND rd.transaction_type IN ('DEBIT', 'CREDIT')
                LEFT JOIN allotment_allotmentitems ai
                    ON ai.item_id = lii.id
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
    ]
