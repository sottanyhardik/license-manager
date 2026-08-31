"""Extraction reconciliation for the presentation-only Financial Ledger PDF."""
from datetime import date
from decimal import Decimal
import re
from unittest.mock import patch

from pypdf import PdfReader

from apps.license.services.exporters.financial_ledger_pdf_renderer import (
    DETAIL_AMOUNT_WIDTHS,
    DETAIL_DESCRIPTION_WIDTHS,
    PRINTABLE_WIDTH,
    render_financial_ledger_pdf,
)


def _license():
    purchase = {
        "id": 501, "date": date(2025, 12, 1), "type": "PURCHASE", "company_id": 7,
        "company_name": "LABDHI MERCANTILE LLP", "party_name": "Golden Supplier",
        "item_names": ["Golden Item A", "Golden Item B"], "purchase_amount": Decimal("192806.27"),
        "sale_amount": None, "rate": Decimal("88.10"), "purchase_bill_amount": Decimal("4583719.00"),
        "sale_bill_amount": None, "license_running_balance": Decimal("116485.77"),
        "profit_loss_inr": None,
    }
    sale = {
        "id": 502, "date": date(2026, 1, 15), "type": "SALE", "company_id": 7,
        "company_name": "LABDHI MERCANTILE LLP", "party_name": "Golden Buyer",
        "item_names": ["Golden Item A"], "purchase_amount": None, "sale_amount": Decimal("76320.50"),
        "rate": None, "purchase_bill_amount": None, "sale_bill_amount": Decimal("6524056.00"),
        "license_running_balance": Decimal("116485.77"), "profit_loss_inr": Decimal("1940337.00"),
    }
    return {
        "license_id": 1, "license_number": "0310833996", "license_type": "DFIA",
        "license_date": date(2025, 10, 1), "first_purchase_date": date(2025, 12, 1),
        "expiry_date": date(2027, 9, 30), "exporter_name": "Golden Exporter", "sion_norms": "E-1",
        "has_purchase_bill": True, "opening_display": None,
        "display_transactions": [purchase, sale],
        "summary": {
            "total_purchase": Decimal("192806.27"), "current_balance": Decimal("116485.77"),
            "total_purchase_bill_inr": Decimal("4583719.00"),
            "total_sale_bill_inr": Decimal("6524056.00"),
            "total_profit_loss": Decimal("1940337.00"), "profit_state": "PROFIT",
        },
        "company_groups": [{
            "company_id": 7, "company_name": "LABDHI MERCANTILE LLP",
            "purchase_total": Decimal("4583719.00"), "sale_total": Decimal("6524056.00"),
            "purchase_value": Decimal("192806.27"), "sale_value": Decimal("76320.50"),
            "current_balance": Decimal("116485.77"), "profit_loss": Decimal("1940337.00"),
        }],
    }


def _extract(data):
    return re.sub(r"\s+", " ", "\n".join(
        page.extract_text() or "" for page in PdfReader(render_financial_ledger_pdf(data)).pages
    ))


def test_list_pdf_extracts_canonical_financial_summary_verbatim():
    license_data = _license()
    row = {
        "license_id": 1, "license_number": "0310833996", "license_type": "DFIA",
        "license_date": date(2025, 10, 1), "first_purchase_date": date(2025, 12, 1),
        "sion_norms": "E-1", "current_balance": Decimal("116485.77"),
        "purchase_bill_inr": Decimal("4583719.00"), "sale_bill_inr": Decimal("6524056.00"),
        "profit_loss_inr": Decimal("1940337.00"), "profit_state": "PROFIT",
    }
    text = _extract({
        "scope": "list", "licenses": [license_data], "summary": {},
        "company_groups": [{
            "company_id": 7, "company_name": "LABDHI MERCANTILE LLP",
            "licenses": [row],
            "sion_groups": [{
                "sion_norm": "E-1", "sion_label": "E-1", "licenses": [row], "license_count": 1,
                "total_balance": Decimal("116485.77"),
                "total_purchase_bill_inr": Decimal("4583719.00"),
                "total_sale_bill_inr": Decimal("6524056.00"),
                "total_profit_loss_inr": Decimal("1940337.00"),
            }],
            "total_balance": Decimal("116485.77"), "total_purchase_bill_inr": Decimal("4583719.00"),
            "total_sale_bill_inr": Decimal("6524056.00"), "total_profit_loss_inr": Decimal("1940337.00"),
        }],
        "grand_total": {
            "license_count": 1, "total_balance": Decimal("116485.77"),
            "total_purchase_bill_inr": Decimal("4583719.00"),
            "total_sale_bill_inr": Decimal("6524056.00"),
            "total_profit_loss_inr": Decimal("1940337.00"),
        },
    })
    for expected in (
        "FINANCIAL TRADE LEDGER", "LABDHI MERCANTILE LLP", "0310833996", "01-Dec-2025",
        "E-1", "1,16,485.77", "45,83,719.00", "65,24,056.00", "19,40,337.00",
        "LICENSE LEDGER STATEMENT", "Golden Supplier", "Golden Buyer", "PURCHASE", "SALE",
    ):
        assert expected in text


def test_list_pdf_consumes_canonical_sion_groups_and_empty_group_once_each():
    def row(number, norm, purchase, sale):
        return {
            "license_id": number, "license_number": f"LIC-{number}", "license_type": "DFIA",
            "license_date": date(2026, 1, number), "first_purchase_date": date(2026, 1, number),
            "sion_norms": norm, "current_balance": Decimal("10.00"),
            "purchase_bill_inr": Decimal(purchase), "sale_bill_inr": Decimal(sale),
            "profit_loss_inr": Decimal(sale) - Decimal(purchase),
        }

    # The composite norm is a single canonical group.  PDF must not split it
    # into two groups or duplicate its financial/license row.
    composite = row(1, "E1, E5", "100.00", "150.00")
    empty = row(2, "", "200.00", "175.00")
    groups = [
        {"sion_norm": "E1, E5", "sion_label": "E1, E5", "licenses": [composite],
         "license_count": 1, "total_balance": Decimal("10.00"),
         "total_purchase_bill_inr": Decimal("100.00"), "total_sale_bill_inr": Decimal("150.00"),
         "total_profit_loss_inr": Decimal("50.00")},
        {"sion_norm": "", "sion_label": "N/A / EMPTY", "licenses": [empty],
         "license_count": 1, "total_balance": Decimal("10.00"),
         "total_purchase_bill_inr": Decimal("200.00"), "total_sale_bill_inr": Decimal("175.00"),
         "total_profit_loss_inr": Decimal("-25.00")},
    ]
    text = _extract({
        "scope": "list", "licenses": [], "summary": {},
        "company_groups": [{
            "company_id": 7, "company_name": "LABDHI MERCANTILE LLP", "sion_groups": groups,
            "total_balance": Decimal("20.00"), "total_purchase_bill_inr": Decimal("300.00"),
            "total_sale_bill_inr": Decimal("325.00"), "total_profit_loss_inr": Decimal("25.00"),
        }],
        "grand_total": {"license_count": 2, "total_balance": Decimal("20.00"),
                        "total_purchase_bill_inr": Decimal("300.00"),
                        "total_sale_bill_inr": Decimal("325.00"),
                        "total_profit_loss_inr": Decimal("25.00")},
    })
    assert "SION: E1, E5" in text
    assert "SION: N/A / EMPTY" in text
    assert text.count("LIC-1") == 1
    assert text.count("LIC-2") == 1
    assert "COMPANY TOTAL — LABDHI MERCANTILE LLP" in text
    assert "GRAND TOTAL" in text


def test_detail_pdf_extracts_rows_parties_items_and_canonical_totals():
    text = _extract({"scope": "detail", "licenses": [_license()], "summary": {}})
    for expected in (
        "LICENSE LEDGER STATEMENT", "Golden Exporter", "Golden Supplier", "Golden Buyer",
        "Golden Item A", "Golden Item B", "PURCHASE", "SALE", "1,92,806.27", "76,320.50",
        "45,83,719.00", "65,24,056.00", "1,16,485.77", "19,40,337.00",
        "LICENSE TOTAL — 0310833996 · LABDHI MERCANTILE LLP",
    ):
        assert expected in text
    assert "N/A" not in text


def test_pdf_renderer_performs_no_database_query():
    # Any accidental ORM evaluation reaches CursorWrapper.execute and fails.
    with patch("django.db.backends.utils.CursorWrapper.execute", side_effect=AssertionError("PDF queried DB")):
        pdf = render_financial_ledger_pdf({"scope": "detail", "licenses": [_license()], "summary": {}})
    assert pdf.getvalue().startswith(b"%PDF")


def test_every_rendered_page_is_a4_portrait_not_a_fallback_size():
    """The statement contract is A4 portrait for both detail and list pages."""
    reader = PdfReader(render_financial_ledger_pdf({"scope": "detail", "licenses": [_license()], "summary": {}}))
    assert reader.pages
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.28) <= 1
        assert abs(float(page.mediabox.height) - 841.89) <= 1


def test_0311055282_portrait_layout_keeps_complete_canonical_totals_inside_the_print_frame():
    """Regression: no formatted amount may be forced through the right border."""
    data = _license()
    data["license_number"] = "0311055282"  # leading zero is part of the identifier.
    purchases = Decimal("799999.96")
    sales = (Decimal("650000.00"), Decimal("6900.39"), Decimal("48597.90"))
    sale_bills = (Decimal("1519243.00"), Decimal("64924.00"), Decimal("457245.00"))
    data["display_transactions"][0].update(purchase_amount=purchases, purchase_bill_amount=Decimal("1700076.00"))
    data["display_transactions"][1].update(sale_amount=sales[0], sale_bill_amount=sale_bills[0], profit_loss_inr=Decimal("341336.00"))
    for index in (1, 2):
        row = dict(data["display_transactions"][1])
        row.update(id=502 + index, sale_amount=sales[index], sale_bill_amount=sale_bills[index], profit_loss_inr=None)
        data["display_transactions"].append(row)
    data["summary"].update(total_purchase=purchases, current_balance=Decimal("94501.67"),
                           total_purchase_bill_inr=Decimal("1700076.00"), total_sale_bill_inr=sum(sale_bills),
                           total_profit_loss=Decimal("341336.00"))
    data["company_groups"][0].update(purchase_total=Decimal("1700076.00"), sale_total=sum(sale_bills),
                                      purchase_value=purchases, sale_value=sum(sales), current_balance=Decimal("94501.67"),
                                      profit_loss=Decimal("341336.00"))

    pdf = render_financial_ledger_pdf({"scope": "detail", "licenses": [data], "summary": {}})
    reader = PdfReader(pdf)
    assert len(reader.pages) == 1  # no blank, duplicate, or summary-only page.
    for page in reader.pages:
        assert abs(float(page.mediabox.width) - 595.28) <= 1
        assert abs(float(page.mediabox.height) - 841.89) <= 1

    # Every renderer table is explicitly constrained to the same 10 mm frame;
    # the two detailed tables avoid an eleven-column numeric overflow.
    assert sum(DETAIL_DESCRIPTION_WIDTHS) <= PRINTABLE_WIDTH
    assert sum(DETAIL_AMOUNT_WIDTHS) <= PRINTABLE_WIDTH
    text = _extract({"scope": "detail", "licenses": [data], "summary": {}})
    for expected in ("0311055282", "7,99,999.96", "7,05,498.29", "17,00,076.00",
                     "20,41,412.00", "94,501.67", "3,41,336.00"):
        assert expected in text
    assert "3,41,336.0 " not in text


def test_long_exporter_is_retained_without_adjacent_summary_text_collision():
    license_data = _license()
    license_data["exporter_name"] = "QUARTERFOLD PRINTABILITIES PRIVATE LIMITED"
    text = _extract({"scope": "detail", "licenses": [license_data], "summary": {}})
    # Paragraph cells retain every word when wrapping onto multiple measured
    # lines; the Total Value label/value stays independently represented.
    assert "QUARTERFOLD PRINTABILITIES PRIVATE LIMITED" in text
    assert "Total Value" in text
    assert "1,92,806.27" in text


def test_no_purchase_bill_uses_approved_status_and_hyphen_empty_values():
    license_data = _license()
    license_data["has_purchase_bill"] = False
    license_data["display_transactions"][0]["purchase_bill_amount"] = None
    text = _extract({"scope": "detail", "licenses": [license_data], "summary": {}})
    assert "NO PURCHASE BILL" in text
    assert "N/A" not in text
