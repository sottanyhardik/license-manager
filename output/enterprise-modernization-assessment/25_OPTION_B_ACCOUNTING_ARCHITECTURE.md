# Option B accounting architecture

Tenant -> LegalEntity -> Chart/Account -> Period -> Voucher -> immutable Lines -> Subledger Allocation -> Bank Account/Statement/Transaction/Match. Posted debit equals credit; source post-once keys; reversals not overwrites; company scoping/audit/period locks. Tax/Tally policy requires CA confirmation.
