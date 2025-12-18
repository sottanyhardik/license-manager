# trade/management/commands/setup_chart_of_accounts.py
"""
Management command to set up initial chart of accounts for Indian accounting
"""

from django.core.management.base import BaseCommand
from trade.models import ChartOfAccounts


class Command(BaseCommand):
    help = 'Set up initial chart of accounts for Indian accounting'

    def handle(self, *args, **options):
        self.stdout.write('Setting up chart of accounts...')

        accounts = [
            # ASSETS (1000-1999)
            {'code': '1000', 'name': 'Current Assets', 'type': 'ASSET', 'parent': None},
            {'code': '1001', 'name': 'Cash in Hand', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1010', 'name': 'Bank Accounts', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1100', 'name': 'Sundry Debtors', 'type': 'ASSET', 'parent': '1000', 'description': 'Accounts Receivable from customers'},
            {'code': '1200', 'name': 'Inventory', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1201', 'name': 'Raw Materials', 'type': 'ASSET', 'parent': '1200'},
            {'code': '1202', 'name': 'Finished Goods', 'type': 'ASSET', 'parent': '1200'},
            {'code': '1300', 'name': 'Prepaid Expenses', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1400', 'name': 'Input Tax Credit', 'type': 'ASSET', 'parent': '1000'},
            {'code': '1401', 'name': 'CGST Input', 'type': 'ASSET', 'parent': '1400'},
            {'code': '1402', 'name': 'SGST Input', 'type': 'ASSET', 'parent': '1400'},
            {'code': '1403', 'name': 'IGST Input', 'type': 'ASSET', 'parent': '1400'},

            {'code': '1500', 'name': 'Fixed Assets', 'type': 'ASSET', 'parent': None},
            {'code': '1501', 'name': 'Land & Building', 'type': 'ASSET', 'parent': '1500'},
            {'code': '1502', 'name': 'Plant & Machinery', 'type': 'ASSET', 'parent': '1500'},
            {'code': '1503', 'name': 'Furniture & Fixtures', 'type': 'ASSET', 'parent': '1500'},
            {'code': '1504', 'name': 'Vehicles', 'type': 'ASSET', 'parent': '1500'},
            {'code': '1505', 'name': 'Computer & Equipment', 'type': 'ASSET', 'parent': '1500'},

            # LIABILITIES (2000-2999)
            {'code': '2000', 'name': 'Current Liabilities', 'type': 'LIABILITY', 'parent': None},
            {'code': '2100', 'name': 'Sundry Creditors', 'type': 'LIABILITY', 'parent': '2000', 'description': 'Accounts Payable to suppliers'},
            {'code': '2200', 'name': 'Output Tax Liability', 'type': 'LIABILITY', 'parent': '2000'},
            {'code': '2201', 'name': 'CGST Output', 'type': 'LIABILITY', 'parent': '2200'},
            {'code': '2202', 'name': 'SGST Output', 'type': 'LIABILITY', 'parent': '2200'},
            {'code': '2203', 'name': 'IGST Output', 'type': 'LIABILITY', 'parent': '2200'},
            {'code': '2300', 'name': 'TDS Payable', 'type': 'LIABILITY', 'parent': '2000'},
            {'code': '2400', 'name': 'Salary Payable', 'type': 'LIABILITY', 'parent': '2000'},
            {'code': '2500', 'name': 'Bank Overdraft', 'type': 'LIABILITY', 'parent': '2000'},

            {'code': '2600', 'name': 'Long Term Liabilities', 'type': 'LIABILITY', 'parent': None},
            {'code': '2601', 'name': 'Bank Loan', 'type': 'LIABILITY', 'parent': '2600'},
            {'code': '2602', 'name': 'Unsecured Loans', 'type': 'LIABILITY', 'parent': '2600'},

            # EQUITY (3000-3999)
            {'code': '3000', 'name': 'Capital', 'type': 'EQUITY', 'parent': None},
            {'code': '3001', 'name': 'Owner Capital', 'type': 'EQUITY', 'parent': '3000'},
            {'code': '3100', 'name': 'Reserves & Surplus', 'type': 'EQUITY', 'parent': None},
            {'code': '3101', 'name': 'Retained Earnings', 'type': 'EQUITY', 'parent': '3100'},
            {'code': '3102', 'name': 'General Reserve', 'type': 'EQUITY', 'parent': '3100'},
            {'code': '3200', 'name': 'Current Year Profit/Loss', 'type': 'EQUITY', 'parent': None},

            # REVENUE (4000-4999)
            {'code': '4000', 'name': 'Sales', 'type': 'REVENUE', 'parent': None},
            {'code': '4001', 'name': 'Domestic Sales', 'type': 'REVENUE', 'parent': '4000'},
            {'code': '4002', 'name': 'Export Sales', 'type': 'REVENUE', 'parent': '4000'},
            {'code': '4100', 'name': 'Other Income', 'type': 'REVENUE', 'parent': None},
            {'code': '4101', 'name': 'Interest Received', 'type': 'REVENUE', 'parent': '4100'},
            {'code': '4102', 'name': 'Discount Received', 'type': 'REVENUE', 'parent': '4100'},
            {'code': '4103', 'name': 'Commission Received', 'type': 'REVENUE', 'parent': '4100'},

            # EXPENSES (5000-5999)
            {'code': '5000', 'name': 'Purchase', 'type': 'EXPENSE', 'parent': None},
            {'code': '5001', 'name': 'Domestic Purchase', 'type': 'EXPENSE', 'parent': '5000'},
            {'code': '5002', 'name': 'Import Purchase', 'type': 'EXPENSE', 'parent': '5000'},

            {'code': '5100', 'name': 'Direct Expenses', 'type': 'EXPENSE', 'parent': None},
            {'code': '5101', 'name': 'Freight Inward', 'type': 'EXPENSE', 'parent': '5100'},
            {'code': '5102', 'name': 'Custom Duty', 'type': 'EXPENSE', 'parent': '5100'},
            {'code': '5103', 'name': 'Import Charges', 'type': 'EXPENSE', 'parent': '5100'},
            {'code': '5104', 'name': 'Packing Charges', 'type': 'EXPENSE', 'parent': '5100'},

            {'code': '5200', 'name': 'Operating Expenses', 'type': 'EXPENSE', 'parent': None},
            {'code': '5201', 'name': 'Salary & Wages', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5202', 'name': 'Rent', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5203', 'name': 'Electricity', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5204', 'name': 'Telephone & Internet', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5205', 'name': 'Office Supplies', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5206', 'name': 'Printing & Stationery', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5207', 'name': 'Vehicle Expenses', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5208', 'name': 'Repairs & Maintenance', 'type': 'EXPENSE', 'parent': '5200'},
            {'code': '5209', 'name': 'Insurance', 'type': 'EXPENSE', 'parent': '5200'},

            {'code': '5300', 'name': 'Selling Expenses', 'type': 'EXPENSE', 'parent': None},
            {'code': '5301', 'name': 'Freight Outward', 'type': 'EXPENSE', 'parent': '5300'},
            {'code': '5302', 'name': 'Advertisement', 'type': 'EXPENSE', 'parent': '5300'},
            {'code': '5303', 'name': 'Commission Paid', 'type': 'EXPENSE', 'parent': '5300'},
            {'code': '5304', 'name': 'Discount Allowed', 'type': 'EXPENSE', 'parent': '5300'},

            {'code': '5400', 'name': 'Financial Expenses', 'type': 'EXPENSE', 'parent': None},
            {'code': '5401', 'name': 'Bank Charges', 'type': 'EXPENSE', 'parent': '5400'},
            {'code': '5402', 'name': 'Interest Paid', 'type': 'EXPENSE', 'parent': '5400'},

            {'code': '5500', 'name': 'Administrative Expenses', 'type': 'EXPENSE', 'parent': None},
            {'code': '5501', 'name': 'Professional Fees', 'type': 'EXPENSE', 'parent': '5500'},
            {'code': '5502', 'name': 'Legal Fees', 'type': 'EXPENSE', 'parent': '5500'},
            {'code': '5503', 'name': 'Audit Fees', 'type': 'EXPENSE', 'parent': '5500'},
            {'code': '5504', 'name': 'License & Registration', 'type': 'EXPENSE', 'parent': '5500'},

            {'code': '5600', 'name': 'Depreciation', 'type': 'EXPENSE', 'parent': None},
            {'code': '5601', 'name': 'Depreciation on Fixed Assets', 'type': 'EXPENSE', 'parent': '5600'},
        ]

        created_count = 0
        updated_count = 0
        parent_map = {}

        # First pass: Create accounts without parents
        for account_data in accounts:
            parent_code = account_data.pop('parent', None)
            code = account_data['code']
            account_type = account_data.pop('type')
            description = account_data.pop('description', '')

            account, created = ChartOfAccounts.objects.update_or_create(
                code=code,
                defaults={
                    'name': account_data['name'],
                    'account_type': account_type,
                    'description': description,
                    'is_active': True
                }
            )

            parent_map[code] = (account, parent_code)

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  Created: {code} - {account.name}'))
            else:
                updated_count += 1
                self.stdout.write(f'  Updated: {code} - {account.name}')

        # Second pass: Set parent relationships
        for code, (account, parent_code) in parent_map.items():
            if parent_code:
                parent_account = parent_map.get(parent_code, (None, None))[0]
                if parent_account:
                    account.parent = parent_account
                    account.save(update_fields=['parent'])

        self.stdout.write(self.style.SUCCESS(f'\nChart of Accounts setup complete!'))
        self.stdout.write(self.style.SUCCESS(f'  Created: {created_count} accounts'))
        self.stdout.write(self.style.SUCCESS(f'  Updated: {updated_count} accounts'))
        self.stdout.write(self.style.SUCCESS(f'  Total: {len(accounts)} accounts'))
