"""Every ledger row_kind the builder can emit must have a PDF row colour (no-DB).

Regression for KeyError 'previous_owner_utilisation' in the financial ledger PDF.
"""
import ast
import re
from pathlib import Path

APPS = Path(__file__).resolve().parents[2]
BUILDER = APPS / "license/services/license_balance_ledger_builder.py"
PDF = APPS / "license/services/exporters/license_balance_pdf.py"


def _emitted_row_kinds():
    return set(re.findall(r"'row_kind':\s*'([a-z_]+)'", BUILDER.read_text()))


def _pdf_color_maps():
    maps = []
    for node in ast.walk(ast.parse(PDF.read_text())):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "ROW_KIND_COLORS" for t in node.targets
        ):
            maps.append({k.value for k in node.value.keys})
    return maps


def test_every_emitted_row_kind_has_a_pdf_colour():
    financial, customs = _pdf_color_maps()  # financial map first, customs second
    emitted = _emitted_row_kinds() - {"final", "boe_child"}  # final: special-cased; boe_child: child rows
    customs_kinds = {k for k in emitted if k.startswith("customs_")}
    assert customs_kinds <= customs, customs_kinds - customs
    assert emitted - customs_kinds <= financial, (emitted - customs_kinds) - financial
