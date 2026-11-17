"""Database-level ledger integrity (defence in depth behind the posting service).

1. Posted/reversed vouchers cannot be deleted; their identity/amount columns cannot change.
   The only allowed transition is POSTED -> REVERSED.
2. Lines of a non-draft voucher cannot be inserted, changed or deleted.
3. A posted voucher must balance (sum debit = sum credit = total > 0, >= 2 lines) at COMMIT
   (deferred constraint trigger, so lines can be written before the status flip).
"""
from django.db import migrations

FORWARD = r"""
CREATE OR REPLACE FUNCTION acct_voucher_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status <> 'DRAFT' THEN
      RAISE EXCEPTION 'accounting: posted voucher % cannot be deleted', OLD.id USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN OLD;
  END IF;
  IF OLD.status = 'DRAFT' THEN
    RETURN NEW;
  END IF;
  IF NEW.entity_id IS DISTINCT FROM OLD.entity_id
     OR NEW.financial_year_id IS DISTINCT FROM OLD.financial_year_id
     OR NEW.voucher_type IS DISTINCT FROM OLD.voucher_type
     OR NEW.number IS DISTINCT FROM OLD.number
     OR NEW.date IS DISTINCT FROM OLD.date
     OR NEW.total IS DISTINCT FROM OLD.total
     OR NEW.idempotency_key IS DISTINCT FROM OLD.idempotency_key
     OR NEW.source_type IS DISTINCT FROM OLD.source_type
     OR NEW.source_id IS DISTINCT FROM OLD.source_id
     OR NEW.reversal_of_id IS DISTINCT FROM OLD.reversal_of_id THEN
    RAISE EXCEPTION 'accounting: posted voucher % is immutable', OLD.id USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF NOT (NEW.status = OLD.status OR (OLD.status = 'POSTED' AND NEW.status = 'REVERSED')) THEN
    RAISE EXCEPTION 'accounting: illegal status change % -> % on voucher %', OLD.status, NEW.status, OLD.id
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER acct_voucher_guard BEFORE UPDATE OR DELETE ON accounting_voucher
  FOR EACH ROW EXECUTE FUNCTION acct_voucher_guard();

CREATE OR REPLACE FUNCTION acct_line_guard() RETURNS trigger AS $$
DECLARE v_status varchar;
BEGIN
  SELECT status INTO v_status FROM accounting_voucher
   WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.voucher_id ELSE NEW.voucher_id END;
  IF v_status IS NOT NULL AND v_status <> 'DRAFT' THEN
    RAISE EXCEPTION 'accounting: lines of posted voucher are immutable' USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF TG_OP = 'UPDATE' AND OLD.voucher_id <> NEW.voucher_id THEN
    SELECT status INTO v_status FROM accounting_voucher WHERE id = OLD.voucher_id;
    IF v_status <> 'DRAFT' THEN
      RAISE EXCEPTION 'accounting: lines of posted voucher are immutable' USING ERRCODE = 'integrity_constraint_violation';
    END IF;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

CREATE TRIGGER acct_line_guard BEFORE INSERT OR UPDATE OR DELETE ON accounting_voucherline
  FOR EACH ROW EXECUTE FUNCTION acct_line_guard();

CREATE OR REPLACE FUNCTION acct_voucher_balanced() RETURNS trigger AS $$
DECLARE d numeric; c numeric; n integer; s varchar;
BEGIN
  SELECT status INTO s FROM accounting_voucher WHERE id = NEW.id;
  IF s IS NULL OR s = 'DRAFT' THEN RETURN NULL; END IF;
  SELECT COALESCE(SUM(debit), 0), COALESCE(SUM(credit), 0), COUNT(*) INTO d, c, n
    FROM accounting_voucherline WHERE voucher_id = NEW.id;
  IF n < 2 OR d <> c OR d <= 0 OR d <> NEW.total THEN
    RAISE EXCEPTION 'accounting: voucher % does not balance (debit %, credit %, total %, lines %)', NEW.id, d, c, NEW.total, n
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NULL;
END $$ LANGUAGE plpgsql;

CREATE CONSTRAINT TRIGGER acct_voucher_balanced AFTER INSERT OR UPDATE ON accounting_voucher
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION acct_voucher_balanced();
"""

REVERSE = r"""
DROP TRIGGER IF EXISTS acct_voucher_balanced ON accounting_voucher;
DROP FUNCTION IF EXISTS acct_voucher_balanced();
DROP TRIGGER IF EXISTS acct_line_guard ON accounting_voucherline;
DROP FUNCTION IF EXISTS acct_line_guard();
DROP TRIGGER IF EXISTS acct_voucher_guard ON accounting_voucher;
DROP FUNCTION IF EXISTS acct_voucher_guard();
"""


class Migration(migrations.Migration):
    dependencies = [("accounting", "0001_initial")]
    operations = [migrations.RunSQL(FORWARD, REVERSE)]
