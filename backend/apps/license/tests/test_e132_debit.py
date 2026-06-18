"""Unit tests for the E132 balance-consuming debit (e132_debit.py)."""
from unittest import TestCase

from apps.license.services.e132_debit import (
    EXHAUSTED,
    NO_MATCH_MESSAGE,
    SUCCESS,
    classify_e132_step,
    compute_e132_debit,
)


def _item(quantity, hs_code='', description='', item_name=''):
    return {'quantity': quantity, 'hs_code': hs_code,
            'description': description, 'item_name': item_name}


class TestClassifyE132Step(TestCase):
    def _key(self, item_key, hs, desc):
        s = classify_e132_step(item_key, hs, desc)
        return s['key'] if s else None

    def test_dairy_description_only(self):
        assert self._key('', '', 'milk 0401') == 'S1'
        assert self._key('', '', 'butter 0405') == 'S1'
        assert self._key('', '', 'cheese 0406') == 'S1'

    def test_dairy_not_matched_by_hsn(self):
        assert self._key('', '04060000', '') is None

    def test_pko_rbd_cashew_foil_flakes(self):
        assert self._key('', '15131000', '') == 'S2'
        assert self._key('', '15119020', '') == 'S3'
        assert self._key('', '08021100', '') == 'S4'
        assert self._key('', '76071190', '') == 'S5'
        assert self._key('', '11041200', '') == 'S6'

    def test_precedence_dairy_beats_pko(self):
        assert self._key('', '15131000', 'contains 0406 solids') == 'S1'

    def test_unmatched(self):
        assert self._key('', '4819', 'carton') is None


class TestFatCascade(TestCase):
    def test_dairy_wins_others_skipped(self):
        res = compute_e132_debit(
            [_item(10, description='milk 0401'),
             _item(10, hs_code='15131000'), _item(10, hs_code='15119020')],
            balance_cif=100000,
        )
        assert len(res['rows']) == 1
        assert res['rows'][0]['product_code'] == '0401 / 0405 / 0406'
        assert res['rows'][0]['unit_rate'] == 5.0

    def test_pko_when_no_dairy(self):
        res = compute_e132_debit(
            [_item(10, hs_code='15131000'), _item(10, hs_code='15119020')],
            balance_cif=100000,
        )
        assert len(res['rows']) == 1
        assert res['rows'][0]['product_code'] == '1513'
        assert res['rows'][0]['unit_rate'] == 2.7


class TestMaxRateWhenItFits(TestCase):
    def test_cashew_max_10(self):
        res = compute_e132_debit([_item(100, hs_code='08021100')], balance_cif=100000)
        assert res['rows'][0]['unit_rate'] == 10.0 and res['rows'][0]['debit_amount'] == 1000.0

    def test_foil_max_4_5(self):
        res = compute_e132_debit([_item(100, hs_code='76071190')], balance_cif=100000)
        assert res['rows'][0]['unit_rate'] == 4.5 and res['rows'][0]['debit_amount'] == 450.0

    def test_flakes_max_0_6(self):
        res = compute_e132_debit([_item(100, hs_code='11041200')], balance_cif=100000)
        assert res['rows'][0]['unit_rate'] == 0.6 and res['rows'][0]['debit_amount'] == 60.0


class TestRateDropsToConsumeBalance(TestCase):
    """The core objective: drop the rate (toward 0) to debit all the balance."""

    def test_foil_drops_below_old_min_of_4(self):
        # 100*4.5 = 450 > 200, so the rate drops to 200/100 = 2.0 (BELOW the old
        # min of 4) and the item consumes the whole balance — Aluminium Foil now
        # gets a $ instead of "Insufficient".
        res = compute_e132_debit([_item(100, hs_code='76071190')], balance_cif=200)
        row = res['rows'][0]
        assert row['status'] == SUCCESS
        assert row['unit_rate'] == 2.0
        assert row['debit_amount'] == 200.0
        assert row['new_balance'] == 0.0
        assert res['fully_consumed'] is True

    def test_foil_rate_can_go_near_zero(self):
        # Tiny balance → very small rate, but still a debit (no refusal).
        res = compute_e132_debit([_item(100, hs_code='76071190')], balance_cif=50)
        row = res['rows'][0]
        assert row['unit_rate'] == 0.5 and row['debit_amount'] == 50.0

    def test_later_item_exhausted_when_balance_gone(self):
        # PKO consumes the whole balance at max; the foil then gets nothing
        # (quantity wasted) but is flagged Balance Exhausted, not Insufficient.
        res = compute_e132_debit(
            [_item(100, hs_code='15131000'), _item(100, hs_code='76071190')],
            balance_cif=270,   # 100*2.7 = 270 exactly
        )
        pko, foil = res['rows']
        assert pko['status'] == SUCCESS and pko['debit_amount'] == 270.0
        assert foil['status'] == EXHAUSTED and foil['debit_amount'] == 0.0
        assert res['fully_consumed'] is True


class TestNoMatch(TestCase):
    def test_no_applicable_code(self):
        res = compute_e132_debit([_item(100, hs_code='4819', description='carton')],
                                 balance_cif=5000)
        assert res['any_match'] is False
        assert res['rows'] == []
        assert res['final_balance'] == 5000.0
        assert 'No applicable E132 norm' in NO_MATCH_MESSAGE


class TestInvariantAndConsumeAll(TestCase):
    def test_total_never_exceeds_opening(self):
        res = compute_e132_debit(
            [_item(1e9, hs_code='15131000'), _item(1e9, hs_code='76071190'),
             _item(1e9, hs_code='11041200')],
            balance_cif=1000,
        )
        assert res['total_debited'] <= 1000.0 + 1e-4
        assert res['final_balance'] >= -1e-9

    def test_real_license_consumes_all_balance(self):
        # PKO -> FOIL (both at max) -> CEREAL FLAKES drops its rate to mop up the
        # remainder, fully consuming the balance.
        res = compute_e132_debit(
            [
                _item(248489.92, hs_code='15131000', description='PALM KERNEL OIL'),
                _item(398468.29, hs_code='76071190', description='ALUMINIUM FOIL'),
                _item(2046533.00, hs_code='11041200', description='CEREALS FLAKES'),
            ],
            balance_cif=2931281.04,
        )
        pko, foil, flakes = res['rows']
        assert pko['unit_rate'] == 2.7 and pko['debit_amount'] == 670922.784
        assert foil['unit_rate'] == 4.5 and foil['debit_amount'] == 1793107.305
        # Flakes drops below its 0.6 max to consume the remaining 4,67,250.951.
        assert flakes['debit_amount'] == 467250.951
        assert flakes['unit_rate'] < 0.6 and flakes['status'] == SUCCESS
        assert res['fully_consumed'] is True
        assert res['final_balance'] == 0.0
        assert abs(res['total_debited'] - 2931281.04) < 1e-4
