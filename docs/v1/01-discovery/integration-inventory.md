# Integration inventory

Code registers Redis/Celery background work, PDF/XLSX/CSV document processing/export, file/media handling and master-data synchronization. Credentials/endpoints and actual external consumers were not inspected. Treat all live integration contracts, schedules and SLAs as **Requires owner/operations verification**.

The related non-HTTP mutation surface is measured rather than assumed: 73 management-command modules and 11 signal/task modules are catalogued in [operational entry-point inventory](operational-entrypoints.md). Their presence is evidence of an operational dependency, not proof that a command is safe to schedule or run in production.
