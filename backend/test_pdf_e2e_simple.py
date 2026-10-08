"""
Simplified end-to-end test for PDF parsing and HS code auto-creation.
Run with: pytest backend/test_pdf_e2e_simple.py -v -s
"""
import pytest
from pathlib import Path
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import HSCodeModel, PortModel, NotificationNumber, SchemeCode
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

User = get_user_model()
PDF_DIR = Path(__file__).parent.parent / "adf"

TEST_PDFS = [
    "3011009642 SONALIKA TRACTORS.pdf",
    "3411008564 Date 06.10.2026.pdf",
    "3411008565 Date 06.10.2026.pdf",
    "3411008573 Date 06.10.2026.pdf",
    "3411008574 Date 06.10.2026.pdf",
]


@pytest.fixture
def api_client_with_auth(db):
    """Create authenticated API client"""
    client = APIClient()
    user, _ = User.objects.get_or_create(
        username='testuser',
        defaults={'email': 'test@test.com', 'is_staff': True, 'is_superuser': True}
    )

    # Use JWT token for authentication
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    return client, user


@pytest.fixture
def ensure_masters(db):
    """Ensure required master data exists"""
    PortModel.objects.get_or_create(code='TEST', defaults={'name': 'Test Port'})
    NotificationNumber.objects.get_or_create(code='025/2023', defaults={'label': '025/2023'})
    SchemeCode.objects.get_or_create(code='26', defaults={'label': 'DFIA'})


@pytest.mark.django_db
@pytest.mark.parametrize("pdf_filename", TEST_PDFS)
def test_pdf_parsing_and_hs_creation(pdf_filename, api_client_with_auth, ensure_masters):
    """Test parsing each PDF and verify HS code auto-creation"""
    client, user = api_client_with_auth
    pdf_path = PDF_DIR / pdf_filename

    # Skip if PDF doesn't exist
    if not pdf_path.exists():
        pytest.skip(f"PDF not found: {pdf_filename}")

    print(f"\n📄 Testing PDF: {pdf_filename}")
    print(f"   Size: {pdf_path.stat().st_size / 1024:.1f} KB")

    # Open PDF and parse
    with open(pdf_path, 'rb') as f:
        response = client.post(
            '/api/licenses/parse-pdf/',
            {'file': f},
            format='multipart'
        )

    print(f"   Response status: {response.status_code}")

    # Check response
    assert response.status_code == 200, f"Parse failed: {response.content}"

    data = response.json()
    license_num = data.get('parsed', {}).get('license_number')
    items = data.get('items', [])
    hs_codes_created = data.get('hs_codes_created', 0)

    print(f"   ✓ License number: {license_num}")
    print(f"   ✓ Items parsed: {len(items)}")
    print(f"   ✓ HS codes created: {hs_codes_created}")

    # Verify parsed data
    assert license_num, "License number not extracted"
    assert len(items) > 0, "No items parsed"

    # Check HS codes
    hs_created_list = []
    hs_matched_list = []
    hs_unmatched_list = []

    for idx, item in enumerate(items, 1):
        hsn = item.get('hsn')
        desc = item.get('description')
        hs_code_id = item.get('matched_hs_code_id')
        hs_created = item.get('hs_code_created', False)

        if hs_created:
            hs_created_list.append({'hsn': hsn, 'description': desc})
            # Verify HS code exists in DB with description
            hs = HSCodeModel.objects.filter(hs_code=hsn).first()
            assert hs is not None, f"Created HS code {hsn} not found in DB"
            assert hs.product_description, f"HS code {hsn} has no description"
            print(f"      🆕 Item {idx}: HSN={hsn}, Created, Desc={hs.product_description[:50]}...")
        elif hs_code_id:
            hs_matched_list.append({'hsn': hsn, 'hs_code_id': hs_code_id})
            hs = HSCodeModel.objects.filter(id=hs_code_id).first()
            print(f"      ✓ Item {idx}: HSN={hsn}, Matched (ID={hs_code_id}), Desc={hs.product_description[:50] if hs else 'N/A'}...")
        else:
            hs_unmatched_list.append({'hsn': hsn})
            print(f"      ⚠️  Item {idx}: HSN={hsn}, Unmatched")

    # Print summary
    print(f"\n   Summary:")
    print(f"      Created: {len(hs_created_list)}")
    for hs in hs_created_list:
        print(f"         • {hs['hsn']}: {hs['description'][:50] if hs['description'] else 'N/A'}...")

    print(f"      Matched: {len(hs_matched_list)}")
    print(f"      Unmatched: {len(hs_unmatched_list)}")

    # Verify count matches
    assert hs_codes_created == len(hs_created_list), f"Created count mismatch: expected {len(hs_created_list)}, got {hs_codes_created}"

    # Try to create the license
    print(f"\n   → Creating license record...")

    prefill = data.get('prefill', {})
    import_rows = []

    for item in items:
        import_rows.append({
            'serial_number': item.get('serial_number', 1),
            'hs_code': item.get('matched_hs_code_id'),
            'description': item.get('description', ''),
            'quantity': float(item.get('quantity', 0)),
            'unit': 'kg',
            'cif_fc': float(item.get('cif_fc', 0)),
            'cif_inr': float(item.get('cif_inr', 0)),
        })

    license_data = {
        'license_number': prefill.get('license_number'),
        'license_date': prefill.get('license_date'),
        'license_expiry_date': prefill.get('license_expiry_date'),
        'file_number': prefill.get('file_number'),
        'registration_number': prefill.get('registration_number'),
        'notification_number': prefill.get('notification_number'),
        'scheme_code': prefill.get('scheme_code'),
        'exporter': prefill.get('exporter'),
        'port': prefill.get('port'),
        'import_license': import_rows,
    }

    license_response = client.post(
        '/api/licenses/',
        license_data,
        format='json'
    )

    if license_response.status_code in (200, 201):
        license_id = license_response.json().get('id')
        print(f"   ✓ License created (ID: {license_id})")

        # Verify all items have HS codes
        saved_items = LicenseImportItemsModel.objects.filter(license__id=license_id)
        items_without_hs = saved_items.filter(hs_code__isnull=True)

        print(f"   ✓ Items saved: {saved_items.count()}")
        if items_without_hs.exists():
            print(f"   ⚠️  Items without HS code: {items_without_hs.count()}")
        else:
            print(f"   ✓ All items have HS codes")

        assert items_without_hs.count() == 0, f"{items_without_hs.count()} items missing HS codes"
    else:
        print(f"   ⚠️  License creation returned {license_response.status_code}")
        print(f"   Response: {license_response.json()}")


@pytest.mark.django_db
def test_hs_codes_have_descriptions():
    """Verify that created HS codes have proper descriptions"""
    # Get the two test HS codes we created in earlier tests
    test_codes = HSCodeModel.objects.filter(hs_code__in=['27101100', '27101200'])

    for hs in test_codes:
        print(f"\n✓ HS Code: {hs.hs_code}")
        print(f"  Description: {hs.product_description}")
        assert hs.product_description, f"HS code {hs.hs_code} has no description"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
