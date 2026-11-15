# Domain memory — licences, CIF, reconciliation

- Canonical balance service: `backend/apps/license/services/balance_calculator.py` (`LicenseBalanceCalculator`).
  Two engines: **customs** (`calculate_balance` = Credit − (non-hidden BOE debit + outstanding allotment))
  and **financial** (`calculate_financial_balance` = Opening + Purchase − Sale − allocation-aware BOE debit − allotment;
  used by `LicenseDetailsModel.get_balance_cif`). Both quantize 2dp and floor at 0 (open decision).
- Allotment CIF is allocation-driven: per item `cif_fc − min(cif_fc, Σ active BOEAllotmentAllocation.allocated_cif_fc)`.
- Hidden BOEs = previous-owner rows; excluded from live calcs, included in the customs ledger running total.
- Purchase/Sale trades do not participate in customs Balance CIF (regression on licence 5211016017 explained in the docstring).
- Domain auditors: `cif-balance-auditor`, `boe-reconciliation-auditor`, `invoice-auditor`, `dgft-dfia-rules-auditor`, `licence-domain-expert`.
