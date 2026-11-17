"""Central posting engine: balance, idempotency, numbering, immutability, reversal, period locks."""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError, InternalError, connection, transaction
from django.db.utils import DatabaseError
from django.test import TestCase

from apps.accounting.models import AccountingAuditEvent, Voucher, VoucherLine, VoucherStatus
from apps.accounting.services import AccountingError
from apps.accounting.services.books import set_period_lock
from apps.accounting.services.chart import system_account
from apps.accounting.services.posting import (
    LineSpec, cr, create_draft, dr, post_draft, post_voucher, reverse_voucher,
)

from . import helpers as h

D = Decimal


class PostingEngineTests(TestCase):
    def setUp(self):
        self.entity = h.books(h.company("Labdhi Mercantile LLP", gst="27AAAFL0000A1Z5"))
        self.cash = h.bank(self.entity).account
        self.capital = system_account(self.entity, "CAPITAL")

    def _post(self, amount="1000.00", key="1", when=date(2026, 5, 1)):
        return post_voucher(entity=self.entity, voucher_type="JOURNAL", voucher_date=when,
                            lines=[dr(self.cash, D(amount)), cr(self.capital, D(amount))], narration="Capital",
                            source_type="TEST", source_id=1, source_version=key)

    def test_balanced_voucher_posts_with_number_and_audit(self):
        v, created = self._post()
        self.assertTrue(created)
        self.assertEqual(v.status, VoucherStatus.POSTED)
        self.assertEqual(v.number, "JNL/2026-27/00001")
        self.assertEqual(v.total, D("1000.00"))
        self.assertTrue(AccountingAuditEvent.objects.filter(action="VOUCHER_POSTED", object_id=v.pk).exists())
        h.immediate_constraints()  # deferred balance trigger passes

    def test_unbalanced_voucher_rejected(self):
        with self.assertRaises(AccountingError):
            post_voucher(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 5, 1),
                         lines=[dr(self.cash, D("10")), cr(self.capital, D("9"))], narration="x",
                         source_type="TEST", source_id=2)

    def test_repeated_delivery_is_idempotent(self):
        v1, c1 = self._post()
        v2, c2 = self._post()
        self.assertEqual(v1.pk, v2.pk)
        self.assertFalse(c2)
        self.assertEqual(Voucher.objects.count(), 1 + 0)  # bank opening not posted (no opening balance)

    def test_numbering_is_sequential_per_type(self):
        a, _ = self._post(key="a")
        b, _ = self._post(key="b")
        self.assertEqual([a.number, b.number], ["JNL/2026-27/00001", "JNL/2026-27/00002"])

    def test_reversal_negates_and_preserves_history(self):
        v, _ = self._post()
        rev = reverse_voucher(v, reason="wrong account")
        v.refresh_from_db()
        self.assertEqual(v.status, VoucherStatus.REVERSED)
        self.assertEqual(rev.reversal_of_id, v.pk)
        lines = {(ln.account_id, ln.debit, ln.credit) for ln in rev.lines.all()}
        self.assertEqual(lines, {(self.cash.pk, D("0"), D("1000.00")), (self.capital.pk, D("1000.00"), D("0"))})
        with self.assertRaises(AccountingError):
            reverse_voucher(v, reason="again")

    def test_locked_period_rejects_posting(self):
        fy = self.entity.financial_years.get()
        set_period_lock(fy.periods.get(period_no=2), True)  # May
        with self.assertRaises(AccountingError) as ctx:
            self._post(when=date(2026, 5, 15))
        self.assertEqual(ctx.exception.code, "period_locked")

    def test_before_books_start_rejected(self):
        with self.assertRaises(AccountingError):
            self._post(when=date(2026, 3, 31))

    def test_manual_draft_does_not_affect_ledger_until_posted(self):
        from apps.accounting.selectors.ledger import account_balance
        draft = create_draft(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 6, 1),
                             lines=[dr(self.cash, D("50")), cr(self.capital, D("50"))], narration="draft")
        self.assertEqual(account_balance(self.cash), D("0"))
        post_draft(draft)
        self.assertEqual(account_balance(self.cash), D("50.00"))

    def test_maker_checker(self):
        from apps.accounts.models import User
        maker = User.objects.create_user(username="maker", password="x")
        self.entity.require_maker_checker = True
        self.entity.save()
        draft = create_draft(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 6, 1),
                             lines=[dr(self.cash, D("5")), cr(self.capital, D("5"))], narration="d", user=maker)
        with self.assertRaises(AccountingError):
            post_draft(draft, user=maker)

    def test_cross_entity_account_rejected(self):
        other = h.books(h.company("Labdhi Global LLP"))
        with self.assertRaises(AccountingError):
            post_voucher(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 5, 1),
                         lines=[dr(self.cash, D("1")), cr(system_account(other, "CAPITAL"), D("1"))],
                         narration="x", source_type="TEST", source_id=3)


class DatabaseTriggerTests(TestCase):
    """The DB refuses edits to posted vouchers even when the service layer is bypassed."""

    def setUp(self):
        self.entity = h.books(h.company("Trigger Co"))
        self.cash = h.bank(self.entity).account
        self.capital = system_account(self.entity, "CAPITAL")
        self.voucher, _ = post_voucher(entity=self.entity, voucher_type="JOURNAL", voucher_date=date(2026, 5, 1),
                                       lines=[dr(self.cash, D("100")), cr(self.capital, D("100"))], narration="x",
                                       source_type="TEST", source_id=1)

    def _expect_db_error(self, fn):
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                fn()
                h.immediate_constraints()

    def test_posted_line_update_blocked(self):
        self._expect_db_error(lambda: VoucherLine.objects.filter(voucher=self.voucher).update(debit=D("1")))

    def test_posted_voucher_delete_blocked(self):
        def go():
            with connection.cursor() as cur:
                cur.execute("DELETE FROM accounting_voucher WHERE id = %s", [self.voucher.pk])
        self._expect_db_error(go)

    def test_posted_voucher_amount_edit_blocked(self):
        self._expect_db_error(lambda: Voucher.objects.filter(pk=self.voucher.pk).update(total=D("5")))

    def test_unbalanced_posted_voucher_blocked_at_commit(self):
        def go():
            v = Voucher.objects.create(entity=self.entity, financial_year=self.voucher.financial_year,
                                       voucher_type="JOURNAL", date=date(2026, 5, 2), total=D("10"), status="DRAFT")
            VoucherLine.objects.create(voucher=v, line_no=1, account=self.cash, debit=D("10"))
            VoucherLine.objects.create(voucher=v, line_no=2, account=self.capital, credit=D("9"))
            Voucher.objects.filter(pk=v.pk).update(status="POSTED", number="JNL/X/1")
        self._expect_db_error(go)

    def test_line_must_be_one_sided(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                v = Voucher.objects.create(entity=self.entity, financial_year=self.voucher.financial_year,
                                           voucher_type="JOURNAL", date=date(2026, 5, 2), total=D("10"))
                VoucherLine.objects.create(voucher=v, line_no=1, account=self.cash, debit=D("10"), credit=D("10"))

    def test_status_flip_to_reversed_allowed(self):
        reverse_voucher(self.voucher, reason="ok")
        h.immediate_constraints()

    def test_line_spec_dataclass_is_frozen(self):
        spec = LineSpec(self.cash, D("1"))
        with self.assertRaises(Exception):
            spec.debit = D("2")  # type: ignore[misc]


_ = InternalError  # imported for readability of expected DB errors
