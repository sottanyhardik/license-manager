"""Seed the deterministic browser-gate licence scenario.

This command is deliberately restricted to a database whose configured name
begins with ``test_``.  It is invoked by the managed E2E harness, never by a
deployment or a developer's shared database.
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from apps.allotment.models import AllotmentItems, AllotmentModel
from apps.bill_of_entry.models import BillOfEntryModel
from apps.core.models import (
    CompanyModel,
    HeadSIONNormsModel,
    ItemNameModel,
    NotificationNumber,
    PortModel,
    SchemeCode,
    SionNormClassModel,
)
from apps.license.models import (
    LicenseDetailsModel,
    LicenseBalance,
    LicenseExportItemModel,
    LicenseImportItemsModel,
    LicenseItemPlan,
    LicensePurchase,
    LicenseReplanRequest,
    SionPlanningAction,
    SionPlanningProfile,
    SionPlanningRule,
)
from apps.trade.models import LicenseTrade


LICENSE_ID = 2509
LICENSE_NUMBER = "3411008090"
ALLOTMENT_INVOICE = "E2E-ALLOTMENT-2509"
AVAILABLE_CIF = Decimal("2066.75")
UNIT_PRICE = Decimal("8.821")
MAX_QUANTITY = Decimal("234.000")
MAX_CIF = Decimal("2064.12")
QUEUE_ITEM_NAME = "E2E QUEUE MATERIAL 2509"
QUEUE_INVOICE = "E2E-QUEUE-2509"
QUEUE_LICENSE_START = 2510
QUEUE_LICENSE_COUNT = 12
QUEUE_POSITION_QUANTITY = Decimal("100.000")
QUEUE_POSITION_CIF = Decimal("1000.00")
BOE_NUMBER = "E2E-BOE-2509"
PURCHASE_INVOICE = "E2E-PURCHASE-2509"
SALE_INVOICE = "E2E-SALE-2509"


def _get_or_report_conflict(model, lookup: dict, defaults: dict, label: str):
    """Create deterministic reference data without rewriting a conflicting seed."""
    value, created = model.objects.get_or_create(**lookup, defaults=defaults)
    if not created:
        conflicts = {
            field: expected
            for field, expected in defaults.items()
            if getattr(value, field) != expected
        }
        if conflicts:
            rendered = ", ".join(f"{field}={expected!r}" for field, expected in conflicts.items())
            raise CommandError(f"Conflicting {label} for {lookup!r}: expected {rendered}.")
    return value


class Command(BaseCommand):
    help = "Seed the isolated canonical browser scenario for licence 2509."

    def _require_disposable_database(self) -> None:
        db_name = str(connection.settings_dict.get("NAME") or "")
        if not db_name.startswith("test_"):
            raise CommandError(
                "seed_browser_2509 only runs against a disposable database named test_*. "
                f"Refusing configured database {db_name!r}."
            )

    @transaction.atomic
    def handle(self, *args, **options):
        self._require_disposable_database()
        existing_at_id = LicenseDetailsModel.objects.filter(pk=LICENSE_ID).first()
        existing_by_number = LicenseDetailsModel.objects.filter(license_number=LICENSE_NUMBER).first()
        if existing_at_id and existing_at_id.license_number != LICENSE_NUMBER:
            raise CommandError(f"Licence id {LICENSE_ID} is occupied by {existing_at_id.license_number!r}.")
        if existing_by_number and existing_by_number.pk != LICENSE_ID:
            raise CommandError(
                f"Licence {LICENSE_NUMBER} exists with id {existing_by_number.pk}; expected {LICENSE_ID}."
            )

        username = os.environ.get("LM_USERNAME", "hardik")
        password = os.environ.get("LM_PASSWORD", "admin@123")
        user_model = get_user_model()
        user, _ = user_model.objects.get_or_create(username=username, defaults={"email": "e2e-browser@example.invalid"})
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        company = _get_or_report_conflict(
            CompanyModel, {"iec": "2509000000"}, {"name": "E2E Browser Exporter"}, "company",
        )
        counterparty = _get_or_report_conflict(
            CompanyModel, {"iec": "2509000001"}, {"name": "E2E Browser Counterparty"}, "counterparty",
        )
        head, _ = HeadSIONNormsModel.objects.get_or_create(name="E2E Browser SION")
        sion = _get_or_report_conflict(
            SionNormClassModel,
            {"norm_class": "E2E2509"},
            {"head_norm": head, "description": "Managed browser gate", "is_active": True},
            "SION",
        )
        item_name = _get_or_report_conflict(
            ItemNameModel,
            {"name": "E2E ALUMINIUM FOIL 2509"},
            {"sion_norm_class": sion, "display_order": 1},
            "canonical item",
        )
        item_name.norms.add(sion)
        queue_item_name = _get_or_report_conflict(
            ItemNameModel,
            {"name": QUEUE_ITEM_NAME},
            {"sion_norm_class": sion, "display_order": 2},
            "queue item",
        )
        queue_item_name.norms.add(sion)

        scheme = _get_or_report_conflict(
            SchemeCode, {"code": "E2E2509"}, {"label": "E2E Browser Scheme"}, "scheme code",
        )
        notification = _get_or_report_conflict(
            NotificationNumber, {"code": "2509"}, {"label": "E2E Browser Notification"}, "notification",
        )
        port = _get_or_report_conflict(
            PortModel, {"code": "E2E"}, {"name": "E2E Browser Port"}, "port",
        )

        license_obj, created = LicenseDetailsModel.objects.get_or_create(
            pk=LICENSE_ID,
            defaults={
                "license_number": LICENSE_NUMBER,
                "license_date": date.today() - timedelta(days=30),
                "license_expiry_date": date.today() + timedelta(days=365),
                "exporter": company,
                "scheme_code": scheme,
                "notification_number": notification,
                "port": port,
            },
        )
        if not created:
            license_obj.license_date = date.today() - timedelta(days=30)
            license_obj.license_expiry_date = date.today() + timedelta(days=365)
            license_obj.exporter = company
            license_obj.scheme_code = scheme
            license_obj.notification_number = notification
            license_obj.port = port
            license_obj.save(update_fields=[
                "license_date", "license_expiry_date", "exporter", "scheme_code",
                "notification_number", "port",
            ])

        profile, _ = SionPlanningProfile.objects.get_or_create(
            stable_key="E2E2509:PROFILE",
            defaults={
                "sion": sion,
                "strategy_type": "ACTION_PIPELINE",
                "config": {"allocation": {"mode": "SEQUENTIAL_WATERFALL"}},
                "version": 1,
                "is_active": False,
            },
        )
        if profile.sion_id != sion.pk:
            raise CommandError("Conflicting planning profile E2E2509:PROFILE belongs to another SION.")
        rule, _ = SionPlanningRule.objects.get_or_create(
            stable_key="E2E2509:RULE:001",
            defaults={
                "sion": sion,
                "name": "E2E ALUMINIUM FOIL 2509",
                "execution_output": "E2E ALUMINIUM FOIL 2509",
                "import_item": item_name,
                "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "ALUMINIUM FOIL"},
                "max_unit_price": UNIT_PRICE,
                "unit": "kg",
                "priority": 1,
                "is_active": True,
                "strategy": "STANDARD",
            },
        )
        if rule.sion_id != sion.pk or rule.import_item_id != item_name.pk:
            raise CommandError("Conflicting planning rule E2E2509:RULE:001 has different canonical references.")
        queue_rule, _ = SionPlanningRule.objects.get_or_create(
            stable_key="E2E2509:RULE:QUEUE",
            defaults={
                "sion": sion,
                "name": QUEUE_ITEM_NAME,
                "execution_output": QUEUE_ITEM_NAME,
                "import_item": queue_item_name,
                "expression": {"field": "DESCRIPTION", "operator": "CONTAINS", "value": "E2E QUEUE"},
                "max_unit_price": Decimal("10.000"),
                "unit": "kg",
                "priority": 2,
                "is_active": True,
                "strategy": "STANDARD",
            },
        )
        if queue_rule.sion_id != sion.pk or queue_rule.import_item_id != queue_item_name.pk:
            raise CommandError("Conflicting planning rule E2E2509:RULE:QUEUE has different canonical references.")
        action, _ = SionPlanningAction.objects.get_or_create(
            profile=profile,
            stable_key="E2E2509:ACTION:001",
            defaults={
                "action_type": "ALLOCATE",
                "priority": 1,
                "config": {"mode": "SEQUENTIAL_WATERFALL"},
                "version": 1,
                "is_active": True,
            },
        )
        if action.action_type != "ALLOCATE" or action.priority != 1:
            raise CommandError("Conflicting planning action E2E2509:ACTION:001.")
        if not profile.is_active:
            profile.is_active = True
            profile.save(update_fields=["is_active"])

        LicenseExportItemModel.objects.update_or_create(
            license=license_obj,
            description="E2E browser credit",
            defaults={"item": item_name, "norm_class": sion, "net_quantity": Decimal("500.00"), "cif_fc": AVAILABLE_CIF},
        )
        import_item, _ = LicenseImportItemsModel.objects.update_or_create(
            license=license_obj,
            serial_number=1,
            defaults={
                "description": "E2E ALUMINIUM FOIL 2509",
                "quantity": Decimal("500.000"),
                "available_quantity": Decimal("500.000"),
                "cif_fc": AVAILABLE_CIF,
            },
        )
        import_item.items.set([item_name])
        LicenseItemPlan.objects.filter(import_item=import_item).delete()
        LicenseItemPlan.objects.create(
            import_item=import_item,
            license=license_obj,
            item_name=item_name,
            planning_rule=rule,
            planning_rule_version=rule.version,
            planning_rule_priority=rule.priority,
            planned_quantity=MAX_QUANTITY,
            planned_cif_fc=MAX_CIF,
            # This field is only a two-decimal historical snapshot; the
            # canonical Max price remains on the allotment below.
            unit_price=Decimal("8.82"),
            remaining_quantity=MAX_QUANTITY,
            remaining_cif_fc=MAX_CIF,
            allocation_provenance={"source": "managed_browser_seed", "canonical_unit_price": str(UNIT_PRICE)},
        )
        allotment, _ = AllotmentModel.objects.update_or_create(
            invoice=ALLOTMENT_INVOICE,
            defaults={
                "company": company,
                "item_name": item_name.name,
                "planning_target_item": item_name,
                "planning_mapping_status": "MAPPED",
                "planning_mapping_source": "managed_browser_seed",
                "required_quantity": Decimal("234.299"),
                "unit_value_per_unit": UNIT_PRICE,
                "exchange_rate": Decimal("1.000000"),
                "is_allotted": False,
            },
        )
        # The browser gate deliberately performs mutations.  Reset only its
        # own deterministic parent rows so rerunning the supported command
        # yields exactly the same authoritative fixture state.
        AllotmentItems.objects.filter(allotment=allotment).delete()

        queue_allotment, _ = AllotmentModel.objects.update_or_create(
            invoice=QUEUE_INVOICE,
            defaults={
                "company": company,
                "item_name": QUEUE_ITEM_NAME,
                "planning_target_item": queue_item_name,
                "planning_mapping_status": "MAPPED",
                "planning_mapping_source": "managed_browser_seed",
                "required_quantity": Decimal("1000.000"),
                "unit_value_per_unit": Decimal("10.000"),
                "exchange_rate": Decimal("1.000000"),
                "is_allotted": False,
            },
        )
        AllotmentItems.objects.filter(allotment=queue_allotment).delete()

        # Populate the other operational lists through their supported domain
        # models.  These are intentionally modest headers: browser checks need
        # genuine persisted records without fabricating financial calculations.
        boe, _ = BillOfEntryModel.objects.update_or_create(
            bill_of_entry_number=BOE_NUMBER,
            bill_of_entry_date=date.today(),
            defaults={
                "company": company,
                "port": port,
                "exchange_rate": Decimal("1.0000"),
                "product_name": item_name.name,
                "invoice_no": "E2E-BOE-INVOICE-2509",
                "invoice_date": date.today(),
                "planning_target_item": item_name,
                "planning_mapping_status": "MAPPED",
                "planning_mapping_source": "managed_browser_seed",
            },
        )
        boe.allotment.set([allotment])
        LicensePurchase.objects.update_or_create(
            license=license_obj,
            invoice_number=PURCHASE_INVOICE,
            defaults={
                "purchasing_entity": company,
                "supplier": counterparty,
                "invoice_date": date.today(),
                "mode": LicensePurchase.MODE_AMOUNT,
                "amount_source": LicensePurchase.SRC_CIF_INR,
                "cif_inr": Decimal("89283.10"),
                "markup_pct": Decimal("100.000000"),
                "amount_inr": Decimal("89283.10"),
            },
        )
        purchase_trade, _ = LicenseTrade.objects.update_or_create(
            direction=LicenseTrade.DIR_PURCHASE,
            from_company=counterparty,
            invoice_number=PURCHASE_INVOICE,
            defaults={
                "to_company": company,
                "invoice_date": date.today(),
                "license_type": LicenseTrade.LICENSE_TYPE_DFIA,
                "subtotal_amount": Decimal("89283.10"),
                "total_amount": Decimal("89283.10"),
                "remarks": "Managed browser purchase fixture",
            },
        )
        purchase_trade.boes.set([boe])
        sale_trade, _ = LicenseTrade.objects.update_or_create(
            direction=LicenseTrade.DIR_SALE,
            to_company=counterparty,
            invoice_number=SALE_INVOICE,
            defaults={
                "from_company": company,
                "invoice_date": date.today(),
                "license_type": LicenseTrade.LICENSE_TYPE_DFIA,
                "subtotal_amount": Decimal("80359.10"),
                "total_amount": Decimal("80359.10"),
                "remarks": "Managed browser sale fixture",
            },
        )
        sale_trade.boes.set([boe])

        # Twelve independently eligible positions make the browser test prove
        # the real server-backed 10-item queue and its 11th-item refill.
        for offset in range(QUEUE_LICENSE_COUNT):
            queue_license_id = QUEUE_LICENSE_START + offset
            queue_license_number = f"3411009{offset + 1:03d}"
            queue_license, _ = LicenseDetailsModel.objects.get_or_create(
                pk=queue_license_id,
                defaults={
                    "license_number": queue_license_number,
                    "license_date": date.today() - timedelta(days=30),
                    "license_expiry_date": date.today() + timedelta(days=365),
                    "exporter": company,
                    "scheme_code": scheme,
                    "notification_number": notification,
                    "port": port,
                },
            )
            if queue_license.license_number != queue_license_number:
                raise CommandError(f"Queue licence id {queue_license_id} is occupied by another licence.")
            queue_license.license_date = date.today() - timedelta(days=30)
            queue_license.license_expiry_date = date.today() + timedelta(days=365)
            queue_license.exporter = company
            queue_license.scheme_code = scheme
            queue_license.notification_number = notification
            queue_license.port = port
            queue_license.save(update_fields=[
                "license_date", "license_expiry_date", "exporter", "scheme_code",
                "notification_number", "port",
            ])
            LicenseExportItemModel.objects.update_or_create(
                license=queue_license,
                description=f"{QUEUE_ITEM_NAME} credit {offset + 1}",
                defaults={
                    "item": queue_item_name,
                    "norm_class": sion,
                    "net_quantity": QUEUE_POSITION_QUANTITY,
                    "cif_fc": QUEUE_POSITION_CIF,
                },
            )
            queue_import, _ = LicenseImportItemsModel.objects.update_or_create(
                license=queue_license,
                serial_number=1,
                defaults={
                    "description": QUEUE_ITEM_NAME,
                    "quantity": QUEUE_POSITION_QUANTITY,
                    "available_quantity": QUEUE_POSITION_QUANTITY,
                    "cif_fc": QUEUE_POSITION_CIF,
                },
            )
            queue_import.items.set([queue_item_name])
            LicenseBalance.objects.update_or_create(
                license=queue_license,
                defaults={"balance_cif": QUEUE_POSITION_CIF},
            )
            LicenseItemPlan.objects.filter(import_item=queue_import).delete()
            LicenseItemPlan.objects.create(
                import_item=queue_import,
                license=queue_license,
                item_name=queue_item_name,
                planning_rule=queue_rule,
                planning_rule_version=queue_rule.version,
                planning_rule_priority=queue_rule.priority,
                planned_quantity=QUEUE_POSITION_QUANTITY,
                planned_cif_fc=QUEUE_POSITION_CIF,
                unit_price=Decimal("10.000"),
                remaining_quantity=QUEUE_POSITION_QUANTITY,
                remaining_cif_fc=QUEUE_POSITION_CIF,
                allocation_provenance={"source": "managed_browser_seed"},
            )
        # Signals may have queued a request while the graph was built.  The
        # seed represents an already persisted current plan, so clear only
        # this licence's seed-time work and make the revisions equal.
        LicenseReplanRequest.objects.filter(license=license_obj).delete()
        LicenseDetailsModel.objects.filter(pk=license_obj.pk).update(
            planning_source_revision=1,
            planning_applied_revision=1,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded licence {LICENSE_NUMBER} (id={license_obj.pk}), allotment={allotment.pk}, "
            f"queue_allotment={queue_allotment.pk}, queue_licences={QUEUE_LICENSE_COUNT}, "
            f"max={MAX_QUANTITY}/{MAX_CIF}."
        ))
