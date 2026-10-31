# Exception-handling standards - rebuild target

| Category | API / transaction behaviour | User outcome | Audit / recovery |
|---|---|---|---|
| Validation | 400 with field-specific stable error code; no write | Clear correction guidance | Structured validation event where material |
| Permission/company scope | 403/404 as policy dictates; no information leak | Generic safe denial | Security event with actor/company/target category |
| Conflict/idempotency | 409 or accepted prior-operation result; no duplicate debit/post | Explain duplicate/in-progress action | Idempotency/correlation key retained |
| Insufficient balance/restriction | Atomic rejection; no partial usage | Show approved basis, remaining amount and rule outcome | Rule snapshot and request context retained |
| Database/broker failure | Rollback atomic operation; retry only idempotent tasks | Retryable service message, no false success | Correlation ID, retry policy, reconciliation queue |
| External import/file | Quarantine invalid file; no partial final import | Row-level error report | File hash, import batch and remediation status |
| Accounting posting | Reject unbalanced/closed-period/duplicate source post | Controlled correction/reversal route | Immutable journal/audit trail |

