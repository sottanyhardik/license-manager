"""Regression coverage for the bounded ``GET /trades/`` list query path."""

from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.trade.models import LicenseTrade, LicenseTradePayment


@pytest.mark.django_db
class TestTradeListQueryBudget:
    def test_list_uses_prefetched_payment_totals_without_n_plus_one(
        self, authenticated_client, test_trade
    ):
        """Nested rows and settlement totals remain correct with bounded queries.

        The list serializes BOEs, DFIA lines, incentive lines, payments and
        linked-trade metadata.  This fixture deliberately expands from one to
        four rows, each with a settlement, to prove payment totals do not add a
        query per trade.
        """
        LicenseTradePayment.objects.create(
            trade=test_trade, amount=Decimal('12.34'), note='initial settlement'
        )
        for index in range(3):
            duplicate = LicenseTrade.objects.create(
                direction=test_trade.direction,
                license_type=test_trade.license_type,
                from_company=test_trade.from_company,
                to_company=test_trade.to_company,
                invoice_number=f'PERF-{index:02d}',
                invoice_date=test_trade.invoice_date,
                total_amount=Decimal('100.00'),
            )
            LicenseTradePayment.objects.create(
                trade=duplicate, amount=Decimal(f'{index + 1}.00'), note='settlement'
            )

        with CaptureQueriesContext(connection) as queries:
            response = authenticated_client.get(reverse('trade:trade-list'), {'page_size': 25})

        assert response.status_code == 200
        payload = response.data['results']
        listed = next(row for row in payload if row['id'] == test_trade.id)

        # The legacy property is the canonical calculation.  Compare its value
        # against the response rather than reproducing financial logic here.
        test_trade.refresh_from_db()
        assert listed['paid_or_received'] == f'{test_trade.paid_or_received:.2f}'
        assert listed['due_amount'] == f'{test_trade.due_amount:.2f}'

        # One count, the header page, and bounded relation prefetches are
        # expected.  This ceiling catches the historical two payment aggregates
        # plus paired-trade lookup for every result while allowing all existing
        # response relations to remain present.
        assert len(queries) <= 10, '\n'.join(query['sql'] for query in queries.captured_queries)

