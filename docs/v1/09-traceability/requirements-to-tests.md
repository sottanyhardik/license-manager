# Requirements-to-tests

Known coverage includes allocation live-CIF/stale-cache/plan isolation tests, role/permission tests, frontend unit tests and E2E assets. [Test-symbol register](test-symbol-register.tsv) enumerates 509 statically indexed test symbols: 252 licence, 109 core, 49 other backend-domain, 5 MDS and 94 other/root symbols. It is a denominator, not a coverage percentage; frontend test modules are separately counted because their test declarations are not represented with the same index kind.

[critical-workflow-test-map.md](critical-workflow-test-map.md) now maps at least
one named test group to every WF-01…WF-16 workflow, and distinguishes executed
backend/frontend tests from discovered-but-unexecuted Playwright/MDS evidence.
This is workflow-level named evidence—not complete regression coverage. M1
must still map exact tests to each endpoint/route/permission/error path.
