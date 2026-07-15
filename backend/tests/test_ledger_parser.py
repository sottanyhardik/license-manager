from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.license.views.ledger_upload import LedgerUploadView


@pytest.mark.parametrize(
    ("filename", "expected_license_numbers"),
    [
        ("L1.csv", ["0311051667", "5211018767"]),
        ("L2.csv", ["0310834974", "0310835522"]),
        ("l3.csv", ["0311054528", "0311007151"]),
    ],
)
def test_ledger_upload_parser_accepts_icegate_csv_exports(filename, expected_license_numbers):
    path = Path(__file__).resolve().parents[2] / "ledgers" / filename
    uploaded_file = SimpleUploadedFile(filename, path.read_bytes(), content_type="text/csv")

    parsed = LedgerUploadView()._parse_file(uploaded_file)

    assert [item["lic_no"] for item in parsed] == expected_license_numbers
    assert all(item["row"] for item in parsed)
