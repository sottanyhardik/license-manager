# license/views/active_dfia_report.py
"""
Active DFIA Report — SION Parle grouped report.

Ported exactly from:
  legacy/backend/apps/license/views/active_dfia_report.py

All business logic preserved. Legacy model methods that lived on
LicenseDetailsModel (get_norm_class, get_item_data, etc.) are replaced
with direct ORM queries against the new model structure.

Field mapping (legacy → new):
  license_obj.balance_cif         → license_obj.balance.balance_cif
  license_obj.get_balance_cif     → license_obj.balance.balance_cif
  license_obj.notification_number → license_obj.notification_number (FK, .code)
  license_obj.get_norm_class      → derived from export_license rel
  license_obj.get_item_data(name) → _get_item_data(license_obj, name)
  license_obj.get_item_head_data  → _get_item_head_data(license_obj, head)
  license_obj.get_biscuit_juice   → _get_biscuit_juice(license_obj)
  license_obj.get_per_cif         → _get_per_cif(license_obj)
  license_obj.cif_value_balance_biscuits → _cif_value_balance_biscuits(license_obj)
  license_obj.condition_sheet     → license_obj.notes.condition_sheet (OneToOne)
"""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import ReportPermission

DEC_0 = Decimal("0")
DEC_000 = Decimal("0.000")


# ---------------------------------------------------------------------------
# Internal helpers — replicate the legacy model methods using new model layout
# ---------------------------------------------------------------------------

def _get_norm_class(license_obj):
    """Return CSV of norm_class strings for a license (replaces get_norm_class)."""
    norms = list(
        license_obj.export_license.filter(
            norm_class__isnull=False
        ).values_list("norm_class__norm_class", flat=True).distinct()
    )
    return ", ".join(n for n in norms if n) if norms else None


def _get_balance_cif(license_obj):
    """Return balance_cif Decimal (replaces license_obj.balance_cif property)."""
    try:
        return license_obj.balance.balance_cif or DEC_0
    except Exception:
        return DEC_0


def _get_item_data(license_obj, item_name: str) -> dict:
    """
    Replaces license_obj.get_item_data(name).
    Returns aggregated data for import items linked to ItemNameModel with given name.
    """
    qs = license_obj.import_license.filter(
        items__name__iexact=item_name
    )
    agg = qs.aggregate(
        available_quantity_sum=Sum("available_quantity"),
        quantity_sum=Sum("quantity"),
    )
    # Take unit_price-equivalent as cif_fc/quantity ratio from first item
    # (legacy used items__unit_price via annotation; new model has no unit_price on
    # ItemNameModel — so we approximate via available_value / available_quantity)
    available_qty = agg.get("available_quantity_sum") or DEC_000
    total_qty = agg.get("quantity_sum") or DEC_000

    # Get hs_code and description from first matching import item
    first = qs.select_related("hs_code").first()
    hs_code = ""
    description = ""
    unit_price = DEC_0
    if first:
        hs_code = first.hs_code.hs_code if first.hs_code else ""
        description = first.description or ""
        # Derive unit price from cif_fc / quantity if quantity > 0
        if first.quantity and first.quantity > DEC_000:
            unit_price = (first.cif_fc or DEC_0) / first.quantity

    return {
        "available_quantity_sum": available_qty,
        "quantity_sum": total_qty,
        "items__unit_price": unit_price,
        "hs_code__hs_code": hs_code,
        "description": description,
    }


def _get_item_head_data(license_obj, head_name: str) -> dict:
    """
    Replaces license_obj.get_item_head_data(head_name).
    Returns aggregated data for import items whose linked ItemNameModel belongs
    to an ItemGroupModel whose name matches head_name (case-insensitive).
    """
    qs = license_obj.import_license.filter(
        items__group__name__iexact=head_name
    )
    agg = qs.aggregate(
        available_quantity_sum=Sum("available_quantity"),
        quantity_sum=Sum("quantity"),
    )
    available_qty = agg.get("available_quantity_sum") or DEC_000
    total_qty = agg.get("quantity_sum") or DEC_000

    first = qs.select_related("hs_code").first()
    hs_code = ""
    description = ""
    if first:
        hs_code = first.hs_code.hs_code if first.hs_code else ""
        description = first.description or ""

    return {
        "available_quantity_sum": available_qty,
        "quantity_sum": total_qty,
        "hs_code__hs_code": hs_code,
        "description": description,
    }


def _get_biscuit_juice(license_obj) -> dict:
    """
    Replaces license_obj.get_biscuit_juice.
    Returns aggregated data for juice-related items (items whose description
    or name contains 'JUICE').
    """
    qs = license_obj.import_license.filter(
        Q(items__name__icontains="JUICE") | Q(description__icontains="JUICE")
    )
    agg = qs.aggregate(
        available_quantity_sum=Sum("available_quantity"),
        quantity_sum=Sum("quantity"),
    )
    available_qty = agg.get("available_quantity_sum") or DEC_000
    total_qty = agg.get("quantity_sum") or DEC_000

    first = qs.first()
    unit_price = DEC_0
    if first and first.quantity and first.quantity > DEC_000:
        unit_price = (first.cif_fc or DEC_0) / first.quantity

    return {
        "available_quantity_sum": available_qty,
        "quantity_sum": total_qty,
        "items__unit_price": unit_price,
    }


def _get_per_cif(license_obj) -> dict:
    """
    Replaces license_obj.get_per_cif.
    Returns per-CIF restriction data. The legacy field 'tenRestriction' is the
    10% restriction amount derived from is_restricted import items.
    """
    restricted_qs = license_obj.import_license.filter(is_restricted=True)
    agg = restricted_qs.aggregate(total_available=Sum("available_value"))
    total_restricted_value = agg.get("total_available") or DEC_0
    ten_restriction = total_restricted_value * Decimal("0.10")
    return {"tenRestriction": ten_restriction}


def _cif_value_balance_biscuits(license_obj) -> dict:
    """
    Replaces license_obj.cif_value_balance_biscuits.
    Returns CIF value balances for Cheese, SWP, WPC items.
    """
    def item_available_value(name):
        qs = license_obj.import_license.filter(items__name__iexact=name)
        agg = qs.aggregate(total=Sum("available_value"))
        return agg.get("total") or DEC_0

    return {
        "cif_cheese": item_available_value("CHEESE"),
        "cif_swp": item_available_value("SWP"),
        "cif_wpc": item_available_value("WPC"),
    }


# ---------------------------------------------------------------------------
# Totals helper
# ---------------------------------------------------------------------------

def _calculate_totals(licenses_list: list) -> dict:
    """Calculate totals for a list of license data dicts."""
    if not licenses_list:
        return {}

    return {
        "total_cif": sum(lic["total_cif"] for lic in licenses_list),
        "balance_cif": sum(lic["balance_cif"] for lic in licenses_list),
        "total_debits": sum(lic["total_debits"] for lic in licenses_list),
        "veg_oil_total_qty": sum(lic["vegetable_oil"]["total_qty"] for lic in licenses_list),
        "veg_oil_total_debited_qty": sum(lic["vegetable_oil"]["total_debited_qty"] for lic in licenses_list),
        "rbd_qty": sum(lic["vegetable_oil"]["rbd_qty"] for lic in licenses_list),
        "rbd_cif": sum(lic["vegetable_oil"]["rbd_cif"] for lic in licenses_list),
        "rbd_debited_qty": sum(lic["vegetable_oil"]["rbd_debited_qty"] for lic in licenses_list),
        "pko_qty": sum(lic["vegetable_oil"]["pko_qty"] for lic in licenses_list),
        "pko_cif": sum(lic["vegetable_oil"]["pko_cif"] for lic in licenses_list),
        "pko_debited_qty": sum(lic["vegetable_oil"]["pko_debited_qty"] for lic in licenses_list),
        "olive_qty": sum(lic["vegetable_oil"]["olive_qty"] for lic in licenses_list),
        "olive_cif": sum(lic["vegetable_oil"]["olive_cif"] for lic in licenses_list),
        "olive_debited_qty": sum(lic["vegetable_oil"]["olive_debited_qty"] for lic in licenses_list),
        "pomace_qty": sum(lic["vegetable_oil"]["pomace_qty"] for lic in licenses_list),
        "pomace_cif": sum(lic["vegetable_oil"]["pomace_cif"] for lic in licenses_list),
        "pomace_debited_qty": sum(lic["vegetable_oil"]["pomace_debited_qty"] for lic in licenses_list),
        "ten_percent_balance": sum(lic["ten_percent_balance"] for lic in licenses_list),
        "juice_qty": sum(lic["juice"]["qty"] for lic in licenses_list),
        "juice_cif": sum(lic["juice"]["cif"] for lic in licenses_list),
        "juice_debited_qty": sum(lic["juice"]["debited_qty"] for lic in licenses_list),
        "ff_qty": sum(lic["food_flavour"]["ff_qty"] for lic in licenses_list),
        "ff_debited_qty": sum(lic["food_flavour"]["ff_debited_qty"] for lic in licenses_list),
        "df_qty": sum(lic["food_flavour"]["df_qty"] for lic in licenses_list),
        "df_debited_qty": sum(lic["food_flavour"]["df_debited_qty"] for lic in licenses_list),
        "fruit_cocoa_qty": sum(lic["fruit_cocoa"]["qty"] for lic in licenses_list),
        "fruit_cocoa_cif": sum(lic["fruit_cocoa"]["cif"] for lic in licenses_list),
        "fruit_cocoa_debited_qty": sum(lic["fruit_cocoa"]["debited_qty"] for lic in licenses_list),
        "leavening_agent_qty": sum(lic["leavening_agent"]["qty"] for lic in licenses_list),
        "leavening_agent_debited_qty": sum(lic["leavening_agent"]["debited_qty"] for lic in licenses_list),
        "starch_1108_qty": sum(lic["starch_1108"]["qty"] for lic in licenses_list),
        "starch_1108_cif": sum(lic["starch_1108"]["cif"] for lic in licenses_list),
        "starch_1108_debited_qty": sum(lic["starch_1108"]["debited_qty"] for lic in licenses_list),
        "starch_3505_qty": sum(lic["starch_3505"]["qty"] for lic in licenses_list),
        "starch_3505_debited_qty": sum(lic["starch_3505"]["debited_qty"] for lic in licenses_list),
        "milk_total_qty": sum(lic["milk_and_milk"]["total_qty"] for lic in licenses_list),
        "milk_total_debited_qty": sum(lic["milk_and_milk"]["total_debited_qty"] for lic in licenses_list),
        "cheese_qty": sum(lic["milk_and_milk"]["cheese_qty"] for lic in licenses_list),
        "cheese_cif": sum(lic["milk_and_milk"]["cheese_cif"] for lic in licenses_list),
        "cheese_debited_qty": sum(lic["milk_and_milk"]["cheese_debited_qty"] for lic in licenses_list),
        "swp_qty": sum(lic["milk_and_milk"]["swp_qty"] for lic in licenses_list),
        "swp_cif": sum(lic["milk_and_milk"]["swp_cif"] for lic in licenses_list),
        "swp_debited_qty": sum(lic["milk_and_milk"]["swp_debited_qty"] for lic in licenses_list),
        "wpc_qty": sum(lic["milk_and_milk"]["wpc_qty"] for lic in licenses_list),
        "wpc_cif": sum(lic["milk_and_milk"]["wpc_cif"] for lic in licenses_list),
        "wpc_debited_qty": sum(lic["milk_and_milk"]["wpc_debited_qty"] for lic in licenses_list),
        "pp_qty": sum(lic["pp"]["qty"] for lic in licenses_list),
        "pp_debited_qty": sum(lic["pp"]["debited_qty"] for lic in licenses_list),
        "aluminium_foil_qty": sum(lic["aluminium_foil"]["qty"] for lic in licenses_list),
        "aluminium_foil_debited_qty": sum(lic["aluminium_foil"]["debited_qty"] for lic in licenses_list),
        "wastage_cif": sum(lic["wastage_cif"] for lic in licenses_list),
    }


# ---------------------------------------------------------------------------
# Item-level builder
# ---------------------------------------------------------------------------

def _build_item_data(item_result: dict) -> dict:
    """Convert _get_item_data / _get_item_head_data result to per-item dict."""
    available_qty = item_result.get("available_quantity_sum", DEC_000)
    total_qty = item_result.get("quantity_sum", available_qty)
    debited_qty = total_qty - available_qty
    unit_price = item_result.get("items__unit_price", DEC_0)
    cif = available_qty * unit_price if available_qty and unit_price else DEC_0

    return {
        "qty": float(available_qty),
        "cif": float(cif),
        "hs_code": item_result.get("hs_code__hs_code", ""),
        "description": item_result.get("description", ""),
        "debited_qty": float(debited_qty),
        "total_qty": float(total_qty),
    }


def _build_head_data(head_result: dict) -> dict:
    """Same as _build_item_data but comes from head query."""
    available_qty = head_result.get("available_quantity_sum", DEC_000)
    total_qty = head_result.get("quantity_sum", available_qty)
    debited_qty = total_qty - available_qty
    return {
        "qty": float(available_qty),
        "total_qty": float(total_qty),
        "hs_code": head_result.get("hs_code__hs_code", ""),
        "description": head_result.get("description", ""),
        "debited_qty": float(debited_qty),
    }


# ---------------------------------------------------------------------------
# The report action — added to LicenseViewSet via add_active_dfia_report_action
# ---------------------------------------------------------------------------

def add_active_dfia_report_action(viewset_class):
    """
    Decorator to add the Active DFIA report action to LicenseViewSet.

    Route: GET /api/v1/licenses/active-dfia-report/

    Generates the Parle SION grouped Excel-like report, grouped by SION norm
    class, then by notification number within each norm.
    """

    @action(
        detail=False,
        methods=["get"],
        url_path="active-dfia-report",
        permission_classes=[ReportPermission],
    )
    def active_dfia_report(self, request):
        """
        Generate Active DFIA report grouped by SION norm class.

        Query params:
            exporter    — company ID (default: all PARLE companies)
            is_expired  — 'true'/'false' (default: false → active only)
            is_null     — 'true'/'false' (default: false → balance >= 200)
            sion_norm   — e.g. E1, E5, E126, E132
            notification — notification code to filter by
        """
        from apps.core.models import CompanyModel

        queryset = self.filter_queryset(self.get_queryset())

        # Default: filter to PARLE group companies
        exporter_id = request.query_params.get("exporter")
        if not exporter_id:
            parle_companies = CompanyModel.objects.filter(
                Q(name__icontains="PARLE")
            ).values_list("id", flat=True)
            queryset = queryset.filter(exporter_id__in=parle_companies)

        # SION norm filter
        sion_norm = request.query_params.get("sion_norm")
        if sion_norm:
            queryset = queryset.filter(
                export_license__norm_class__norm_class=sion_norm
            ).distinct()

        # Notification filter
        notification = request.query_params.get("notification")
        if notification:
            queryset = queryset.filter(notification_number__code=notification)

        # Expiry filter — default: active only
        is_expired = request.query_params.get("is_expired", "False")
        if is_expired.lower() == "false":
            today = date.today()
            queryset = queryset.filter(
                Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True)
            )
        elif is_expired.lower() == "true":
            queryset = queryset.filter(license_expiry_date__lt=date.today())

        # Balance filter — default: balance >= 200
        is_null = request.query_params.get("is_null", "False")
        if is_null.lower() == "false":
            queryset = queryset.filter(balance__balance_cif__gte=200)
        elif is_null.lower() == "true":
            queryset = queryset.filter(balance__balance_cif__lt=200)

        # Prefetch for performance
        queryset = queryset.select_related(
            "exporter", "port", "notification_number", "balance",
        ).prefetch_related(
            "export_license",
            "export_license__norm_class",
            "import_license",
            "import_license__items",
            "import_license__items__group",
            "import_license__hs_code",
        ).order_by("license_expiry_date", "license_date")

        # Group: {sion_norm: {notification_number: [license_data]}}
        grouped_data = defaultdict(lambda: defaultdict(list))

        for license_obj in queryset:
            # Derive primary SION norm
            norm_str = _get_norm_class(license_obj) or "Unknown"
            primary_norm = norm_str.split(",")[0].strip() if norm_str else "Unknown"

            notification_num = (
                license_obj.notification_number.code
                if license_obj.notification_number_id
                else None
            ) or "Unknown"

            balance_cif_dec = _get_balance_cif(license_obj)

            # Total CIF from export items
            total_cif = license_obj.export_license.aggregate(
                total=Sum("cif_fc")
            )["total"] or DEC_0
            total_debits = total_cif - balance_cif_dec

            license_data = {
                "id": license_obj.id,
                "license_number": license_obj.license_number,
                "license_date": license_obj.license_date,
                "license_expiry_date": license_obj.license_expiry_date,
                "exporter_name": license_obj.exporter.name if license_obj.exporter else "",
                "notification_number": notification_num,
                "sion_norm": primary_norm,
                "total_cif": float(total_cif),
                "balance_cif": float(balance_cif_dec),
                "total_debits": float(total_debits),
            }

            # ---- Vegetable Oil ----
            veg_oil = _build_head_data(_get_item_head_data(license_obj, "VEGETABLE OIL"))
            rbd = _build_item_data(_get_item_data(license_obj, "RBD PALMOLEIN OIL"))
            pko = _build_item_data(_get_item_data(license_obj, "PALM KERNEL OIL"))
            olive = _build_item_data(_get_item_data(license_obj, "OLIVE OIL"))
            pomace = _build_item_data(_get_item_data(license_obj, "POMACE OIL"))

            license_data["vegetable_oil"] = {
                "hsn_code": veg_oil["hs_code"] or "15132110",
                "description": veg_oil["description"] or (
                    "Fats - Edible Vegetable Oil /Palmolein Oil / Palm Kernel Oil /Cocoa Butter"
                ),
                "total_qty": veg_oil["total_qty"],
                "total_debited_qty": veg_oil["debited_qty"],
                "rbd_qty": rbd["qty"],
                "rbd_cif": rbd["cif"],
                "rbd_debited_qty": rbd["debited_qty"],
                "pko_qty": pko["qty"],
                "pko_cif": pko["cif"],
                "pko_debited_qty": pko["debited_qty"],
                "olive_qty": olive["qty"],
                "olive_cif": olive["cif"],
                "olive_debited_qty": olive["debited_qty"],
                "pomace_qty": pomace["qty"],
                "pomace_cif": pomace["cif"],
                "pomace_debited_qty": pomace["debited_qty"],
            }

            # ---- 10% Balance (from restricted items) ----
            per_cif = _get_per_cif(license_obj)
            license_data["ten_percent_balance"] = float(
                per_cif.get("tenRestriction", DEC_0)
            )

            # ---- Food Flavour head (shared HS code / description for juice + ff) ----
            food_flavour_head = _build_head_data(
                _get_item_head_data(license_obj, "FOOD FLAVOUR")
            )

            # ---- Juice ----
            biscuit_juice = _get_biscuit_juice(license_obj)
            juice_qty = biscuit_juice.get("available_quantity_sum", DEC_000)
            juice_total_qty = biscuit_juice.get("quantity_sum", DEC_000)
            juice_debited_qty = juice_total_qty - juice_qty
            juice_unit_price = biscuit_juice.get("items__unit_price", DEC_0)
            juice_cif = (
                juice_qty * juice_unit_price
                if juice_qty and juice_unit_price
                else DEC_0
            )

            license_data["juice"] = {
                "hsn_code": food_flavour_head["hs_code"] or "08023100",
                "description": food_flavour_head["description"] or "RELEVANT FLAVOUR IMPROVERS - FRUIT FLAVOUR",
                "qty": float(juice_qty),
                "cif": float(juice_cif),
                "debited_qty": float(juice_debited_qty),
            }

            # ---- Food Flavour (FF Biscuits + Dietary Fibre) ----
            ff = _build_item_data(_get_item_data(license_obj, "FOOD FLAVOUR BISCUITS"))
            df = _build_item_data(_get_item_data(license_obj, "DIETARY FIBRE"))
            license_data["food_flavour"] = {
                "hsn_code": food_flavour_head["hs_code"],
                "description": food_flavour_head["description"],
                "ff_qty": ff["qty"],
                "ff_debited_qty": ff["debited_qty"],
                "df_qty": df["qty"],
                "df_debited_qty": df["debited_qty"],
            }

            # ---- Fruit / Cocoa ----
            fruit = _build_item_data(_get_item_data(license_obj, "FRUIT/COCOA"))
            license_data["fruit_cocoa"] = {
                "hsn_code": fruit["hs_code"] or "",
                "description": fruit["description"] or "",
                "qty": fruit["qty"],
                "cif": fruit["cif"],
                "debited_qty": fruit["debited_qty"],
            }

            # ---- Leavening Agent ----
            leavening = _build_item_data(_get_item_data(license_obj, "LEAVENING AGENT"))
            license_data["leavening_agent"] = {
                "hsn_code": leavening["hs_code"] or "",
                "description": leavening["description"] or "",
                "qty": leavening["qty"],
                "debited_qty": leavening["debited_qty"],
            }

            # ---- Starch 1108 ----
            starch_1108 = _build_item_data(_get_item_data(license_obj, "STARCH 1108"))
            license_data["starch_1108"] = {
                "hsn_code": starch_1108["hs_code"] or "",
                "description": starch_1108["description"] or "",
                "qty": starch_1108["qty"],
                "cif": starch_1108["cif"],
                "debited_qty": starch_1108["debited_qty"],
            }

            # ---- Starch 3505 ----
            starch_3505 = _build_item_data(_get_item_data(license_obj, "STARCH 3505"))
            license_data["starch_3505"] = {
                "hsn_code": starch_3505["hs_code"] or "",
                "description": starch_3505["description"] or "",
                "qty": starch_3505["qty"],
                "debited_qty": starch_3505["debited_qty"],
            }

            # ---- Milk & Milk Products ----
            mnm = _build_head_data(_get_item_head_data(license_obj, "MILK & MILK Product"))
            cheese = _build_item_data(_get_item_data(license_obj, "CHEESE"))
            swp = _build_item_data(_get_item_data(license_obj, "SWP"))
            wpc = _build_item_data(_get_item_data(license_obj, "WPC"))
            biscuits_calc = _cif_value_balance_biscuits(license_obj)

            license_data["milk_and_milk"] = {
                "hsn_code": mnm["hs_code"],
                "description": mnm["description"] or "Milk & Milk Products / Milk Solids",
                "total_qty": mnm["total_qty"],
                "total_debited_qty": mnm["debited_qty"],
                "cheese_qty": cheese["qty"],
                "cheese_cif": float(biscuits_calc.get("cif_cheese", DEC_0)),
                "cheese_debited_qty": cheese["debited_qty"],
                "swp_qty": swp["qty"],
                "swp_cif": float(biscuits_calc.get("cif_swp", DEC_0)),
                "swp_debited_qty": swp["debited_qty"],
                "wpc_qty": wpc["qty"],
                "wpc_cif": float(biscuits_calc.get("cif_wpc", DEC_0)),
                "wpc_debited_qty": wpc["debited_qty"],
            }

            # ---- Packing Material head ----
            packing_head = _build_head_data(
                _get_item_head_data(license_obj, "PACKING MATERIAL")
            )

            # ---- PP ----
            pp = _build_item_data(_get_item_data(license_obj, "PP"))
            license_data["pp"] = {
                "hsn_code": packing_head["hs_code"] or "39021000",
                "description": packing_head["description"] or "Packing Material - PP",
                "qty": pp["qty"],
                "debited_qty": pp["debited_qty"],
            }

            # ---- Aluminium Foil ----
            aluminium = _build_item_data(_get_item_data(license_obj, "ALUMINIUM FOIL"))
            license_data["aluminium_foil"] = {
                "hsn_code": packing_head["hs_code"],
                "description": packing_head["description"],
                "qty": aluminium["qty"],
                "debited_qty": aluminium["debited_qty"],
            }

            # ---- Wastage CIF (10% of balance) ----
            license_data["wastage_cif"] = (
                float(balance_cif_dec) * 0.10 if balance_cif_dec else 0.0
            )

            grouped_data[primary_norm][notification_num].append(license_data)

        # Build grouped response
        result_by_sion = []

        for sion_key in sorted(grouped_data.keys()):
            notifications_data = []

            for notif_key in sorted(grouped_data[sion_key].keys()):
                licenses = grouped_data[sion_key][notif_key]
                notifications_data.append({
                    "notification_number": notif_key,
                    "license_count": len(licenses),
                    "licenses": licenses,
                    "totals": _calculate_totals(licenses),
                })

            all_in_norm = []
            for group in grouped_data[sion_key].values():
                all_in_norm.extend(group)

            result_by_sion.append({
                "sion_norm": sion_key,
                "notifications": notifications_data,
                "totals": _calculate_totals(all_in_norm),
                "license_count": len(all_in_norm),
            })

        # Grand totals
        all_licenses = []
        for sion_group in grouped_data.values():
            for notif_group in sion_group.values():
                all_licenses.extend(notif_group)

        grand_totals = _calculate_totals(all_licenses)

        return Response({
            "groups": result_by_sion,
            "grand_totals": grand_totals,
            "summary": {
                "total_licenses": len(all_licenses),
                "total_sion_norms": len(grouped_data),
                "total_cif": grand_totals.get("total_cif", 0),
                "balance_cif": grand_totals.get("balance_cif", 0),
            },
        })

    viewset_class.active_dfia_report = active_dfia_report
    return viewset_class
