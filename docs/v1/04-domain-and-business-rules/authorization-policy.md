# Authorization policy

Current verified policy is role-based and centralized. The current canonical suite includes tests that documented legitimate roles can read multiple companies and that narrower roles do not receive sensitive fields; this is **Verified by test**, not an assumption of tenant isolation. V1 must add an approved object/company access matrix only after D1; frontend guards are usability affordances, never authority. Unknown ledger write actions fail closed.

Consequently, “cross-company denial” is not a current acceptance criterion: it would contradict tested multi-company-read behavior unless the owner approves a new policy. The V1 security test plan must instead distinguish (a) current role-boundary denials, (b) approved cross-company visibility, and (c) any future object/company-scope denials.

Company-isolation terminology is therefore reserved for a specific data/calculation contract only when a test names it; it is never used as shorthand for tenant isolation or endpoint-level access denial.
