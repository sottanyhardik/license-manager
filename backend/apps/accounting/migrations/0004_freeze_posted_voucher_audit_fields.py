"""Freeze the audit/identity columns of a posted voucher too (DB review finding).

0002 froze the amount/identity columns. A posted voucher's narration and its posting evidence
(posted_by/posted_at/created_by) and source tags must not change either; corrections go through a
reversal. ``modified_on/modified_by`` and ``attachment`` stay writable (status flip, supporting docs).
The reverse step restores exactly the 0002 function.
"""
from django.db import migrations

GUARD_BODY = r"""
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
     OR NEW.reversal_of_id IS DISTINCT FROM OLD.reversal_of_id
     __EXTRA__ THEN
    RAISE EXCEPTION 'accounting: posted voucher % is immutable', OLD.id USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  IF NOT (NEW.status = OLD.status OR (OLD.status = 'POSTED' AND NEW.status = 'REVERSED')) THEN
    RAISE EXCEPTION 'accounting: illegal status change % -> % on voucher %', OLD.status, NEW.status, OLD.id
      USING ERRCODE = 'integrity_constraint_violation';
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

EXTRA = """OR NEW.narration IS DISTINCT FROM OLD.narration
     OR NEW.posted_by_id IS DISTINCT FROM OLD.posted_by_id
     OR NEW.posted_at IS DISTINCT FROM OLD.posted_at
     OR NEW.created_by_id IS DISTINCT FROM OLD.created_by_id
     OR NEW.source_event IS DISTINCT FROM OLD.source_event
     OR NEW.source_version IS DISTINCT FROM OLD.source_version"""


class Migration(migrations.Migration):
    dependencies = [("accounting", "0003_accounting_roles")]
    operations = [migrations.RunSQL(GUARD_BODY.replace("__EXTRA__", EXTRA), GUARD_BODY.replace("__EXTRA__", ""))]
