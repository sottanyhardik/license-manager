# Database open questions and required approvals

1. Which database/schema version and migrations are deployed in production?
2. Can an authorised encrypted backup be restored to an isolated environment, including uploaded documents and asynchronous job state where required?
3. Which company relationships are legal shared masters versus strict tenant-owned data?
4. What is the authoritative historical retention and correction policy for licences, BOEs, allotments, trades and documents?
5. Which source documents define each AU and 2%, 3%, 5%, 10% restriction, including calculation base, unit, scope, date and override rule?
6. Which stored balance snapshots are contractual historical facts versus regenerable caches?
7. What is the approved treatment of hidden/restored BOEs in operational and historical reports?
8. Does the business permit a maintenance window, or must a target cutover support delta capture/dual-run?
9. What historical depth and opening/cutover policy is required for accounting, and who is the CA approver?

