"""
End-to-end test script for PDF parsing and HS code auto-creation.
Tests all 5 specified PDFs to verify:
- PDF parsing works correctly
- HS codes are created with product descriptions
- All items are properly linked to HS codes
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'lmanagement.settings')
sys.path.insert(0, str(Path(__file__).parent))
django.setup()

from django.contrib.auth import get_user_model
from django.test.client import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.core.models import HSCodeModel, CompanyModel, PortModel, NotificationNumber, SchemeCode
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel

User = get_user_model()

# Test PDFs to parse
TEST_PDFS = [
    "3011009642 SONALIKA TRACTORS.pdf",
    "3411008564 Date 06.10.2026.pdf",
    "3411008565 Date 06.10.2026.pdf",
    "3411008573 Date 06.10.2026.pdf",
    "3411008574 Date 06.10.2026.pdf",
]

PDF_DIR = Path(__file__).parent.parent / "adf"


def setup_test_user():
    """Create or get test user"""
    user, _ = User.objects.get_or_create(
        username='testuser',
        defaults={
            'email': 'test@test.com',
            'is_staff': True,
            'is_superuser': True,
        }
    )
    return user


def get_or_create_masters():
    """Ensure required master data exists"""
    masters = {}

    # Port
    port, _ = PortModel.objects.get_or_create(
        code='TEST',
        defaults={'name': 'Test Port'}
    )
    masters['port'] = port

    # Notification
    notif, _ = NotificationNumber.objects.get_or_create(
        code='025/2023',
        defaults={'label': '025/2023'}
    )
    masters['notification'] = notif

    # Scheme
    scheme, _ = SchemeCode.objects.get_or_create(
        code='26',
        defaults={'label': 'DFIA'}
    )
    masters['scheme'] = scheme

    return masters


def test_pdf_parsing():
    """Test parsing all specified PDFs"""
    print("\n" + "="*80)
    print("END-TO-END PDF PARSING TEST: Auto-Create HS Codes")
    print("="*80 + "\n")

    user = setup_test_user()
    masters = get_or_create_masters()
    client = Client()
    client.force_login(user)

    results = []

    for pdf_filename in TEST_PDFS:
        pdf_path = PDF_DIR / pdf_filename

        if not pdf_path.exists():
            print(f"❌ PDF NOT FOUND: {pdf_filename}")
            results.append({
                'file': pdf_filename,
                'status': 'ERROR',
                'message': 'File not found',
            })
            continue

        print(f"\n📄 Testing: {pdf_filename}")
        print(f"   Path: {pdf_path}")
        print(f"   Size: {pdf_path.stat().st_size / 1024:.1f} KB")

        try:
            # Read PDF file
            with open(pdf_path, 'rb') as f:
                pdf_content = f.read()

            # Upload and parse
            print(f"   → Parsing PDF...")
            response = client.post(
                '/api/licenses/parse-pdf/',
                {'file': SimpleUploadedFile(pdf_filename, pdf_content, content_type='application/pdf')},
                format='multipart'
            )

            if response.status_code != 200:
                print(f"   ❌ Parse failed with status {response.status_code}")
                print(f"   Content-Type: {response.get('Content-Type', 'unknown')}")
                try:
                    data = response.json()
                    print(f"   Error: {data.get('detail', 'Unknown error')}")
                except:
                    print(f"   Response: {response.content[:500]}")
                results.append({
                    'file': pdf_filename,
                    'status': 'ERROR',
                    'message': f"Parse failed: status {response.status_code}",
                })
                continue

            data = response.json()
            license_num = data.get('parsed', {}).get('license_number')
            print(f"   ✓ Parse successful - License: {license_num}")

            # Check parsed data
            parsed = data.get('parsed', {})
            items = data.get('items', [])
            hs_codes_created = data.get('hs_codes_created', 0)

            print(f"   ✓ Company: {data.get('matched_company_name')}")
            print(f"   ✓ Port: {data.get('matched_port_code')}")
            print(f"   ✓ Items parsed: {len(items)}")
            print(f"   ✓ HS codes created: {hs_codes_created}")

            # Verify item details and HS codes
            print(f"\n   Item Details:")
            hs_codes_created_list = []
            hs_codes_matched_list = []

            for idx, item in enumerate(items, 1):
                hsn = item.get('hsn', 'N/A')
                desc = item.get('description', 'N/A')
                hs_code_id = item.get('matched_hs_code_id')
                hs_created = item.get('hs_code_created', False)
                qty = item.get('quantity', 0)

                if hs_created:
                    hs_codes_created_list.append({'hsn': hsn, 'description': desc})
                elif hs_code_id:
                    hs_codes_matched_list.append({'hsn': hsn, 'hs_code_id': hs_code_id})

                status_icon = "🆕" if hs_created else ("✓" if hs_code_id else "⚠️")
                print(f"      {status_icon} Item {idx}: HSN={hsn}, Qty={qty}, Desc={desc[:50]}...")

                if hs_code_id:
                    # Verify HS code exists in DB
                    hs = HSCodeModel.objects.filter(id=hs_code_id).first()
                    if hs:
                        print(f"         → HS Code: {hs.hs_code}, Product: {hs.product_description[:50]}...")

            # Summary
            print(f"\n   Summary:")
            print(f"      Created: {len(hs_codes_created_list)} HS codes")
            for hs in hs_codes_created_list:
                print(f"         • {hs['hsn']}: {hs['description'][:50]}...")

            print(f"      Matched: {len(hs_codes_matched_list)} existing HS codes")

            unmatched = sum(1 for item in items if not item.get('matched_hs_code_id'))
            if unmatched:
                print(f"      ⚠️  Unmatched: {unmatched} items")

            results.append({
                'file': pdf_filename,
                'status': 'SUCCESS',
                'license_number': license_num,
                'items_count': len(items),
                'hs_codes_created': len(hs_codes_created_list),
                'hs_codes_matched': len(hs_codes_matched_list),
                'unmatched': unmatched,
            })

            # Now try to create the actual license to verify it saves
            print(f"\n   → Creating license record...")

            # Build license data from parsed response
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

            # Create license
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
                print(f"   ✓ License created successfully (ID: {license_id})")

                # Verify all items have HS codes
                saved_items = LicenseImportItemsModel.objects.filter(license__id=license_id)
                items_without_hs = saved_items.filter(hs_code__isnull=True)

                if items_without_hs.exists():
                    print(f"   ⚠️  {items_without_hs.count()} items without HS code!")
                else:
                    print(f"   ✓ All {saved_items.count()} items have HS codes assigned")

                results[-1]['license_created'] = True
                results[-1]['license_id'] = license_id
            else:
                print(f"   ❌ License creation failed: {license_response.status_code}")
                error_msg = license_response.json()
                print(f"   Error: {error_msg}")
                results[-1]['license_created'] = False

        except Exception as e:
            print(f"   ❌ Exception: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append({
                'file': pdf_filename,
                'status': 'ERROR',
                'message': str(e),
            })

    # Print final summary
    print("\n" + "="*80)
    print("FINAL SUMMARY")
    print("="*80 + "\n")

    for result in results:
        status_icon = "✅" if result['status'] == 'SUCCESS' else "❌"
        print(f"{status_icon} {result['file']}")

        if result['status'] == 'SUCCESS':
            print(f"   License: {result.get('license_number')}")
            print(f"   Items: {result.get('items_count')}")
            print(f"   HS Created: {result.get('hs_codes_created')} | Matched: {result.get('hs_codes_matched')} | Unmatched: {result.get('unmatched')}")
            print(f"   License Saved: {'✓ Yes' if result.get('license_created') else '❌ No'} (ID: {result.get('license_id', 'N/A')})")
        else:
            print(f"   Error: {result.get('message')}")

    # Verify HS codes in database
    print("\n" + "="*80)
    print("HS CODES IN DATABASE")
    print("="*80 + "\n")

    all_hs_codes = HSCodeModel.objects.all().order_by('-id')[:20]
    print(f"Recent HS Codes (last 20):\n")
    for hs in all_hs_codes:
        print(f"  • {hs.hs_code}: {hs.product_description[:60]}...")

    print(f"\nTotal HS Codes in DB: {HSCodeModel.objects.count()}")

    # Test complete
    print("\n" + "="*80)
    print("✅ TEST COMPLETE")
    print("="*80 + "\n")

    return results


if __name__ == '__main__':
    test_pdf_parsing()
