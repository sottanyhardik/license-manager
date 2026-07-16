#!/usr/bin/env python3
"""Build the stateful audit artifacts for this repository.

The existing `.claude/index` remains the navigation index. This script creates
the Codex audit layer on top of it: per-file status, current checksums, module
rollups, and the prioritized work queue.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_ROOT = REPO_ROOT / "docs" / "audit"
CLAUDE_INDEX = REPO_ROOT / ".claude" / "index"

EXCLUDED_DIR_PARTS = {
    ".git",
    ".cache",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "htmlcov",
    "node_modules",
    "venv",
}

EXCLUDED_PATH_PREFIXES = (
    ".claude/index/CODE_MAP.md",
    ".claude/index/dependents.tsv",
    ".claude/index/imports.tsv",
    ".claude/index/index.log",
    ".claude/index/manifest.json",
    ".claude/index/symbols.tsv",
    "backend/theme/vendor/",
    "exc_pdf/",
)

SOURCE_EXTENSIONS = {
    ".cfg",
    ".conf",
    ".css",
    ".dockerfile",
    ".env",
    ".html",
    ".ini",
    ".js",
    ".json",
    ".jsx",
    ".less",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".scss",
    ".service",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".vue",
    ".yaml",
    ".yml",
}

SOURCE_FILENAMES = {
    ".env.example",
    ".gitignore",
    ".prettierignore",
    "Dockerfile",
    "Makefile",
}

BINARY_OR_GENERATED_EXTENSIONS = {
    ".DS_Store",
    ".eot",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".log",
    ".otf",
    ".pdf",
    ".png",
    ".sqlite3",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".xls",
    ".xlsx",
    ".zip",
}

GENERATED_AUDIT_FILES = {
    "docs/audit/audit-database.json",
    "docs/audit/dashboard.md",
    "docs/audit/repository-knowledge-graph.json",
    "docs/audit/work-queue.md",
}

COMPLETED_VERIFIED_FILES = {
    "backend/apps/allotment/admin.py",
    "backend/apps/allotment/services/allocation_service.py",
    "backend/apps/bill_of_entry/admin.py",
    "backend/apps/bill_of_entry/parsers/boe_pdf.py",
    "backend/apps/bill_of_entry/serializers.py",
    "backend/apps/core/scripts/calculation.py",
    "backend/apps/core/scripts/company_names.py",
    "backend/apps/core/scripts/license_script.py",
    "backend/apps/core/management/commands/sync_from_ge_server.py",
    "backend/apps/core/admin.py",
    "backend/apps/core/authentication.py",
    "backend/apps/core/middleware.py",
    "backend/apps/license/management/commands/update_license_ownership.py",
    "backend/apps/license/views_actions.py",
    "backend/apps/license/serializers/license.py",
    "backend/apps/license/tasks.py",
    "backend/apps/license/views/item_pivot_report.py",
    "backend/apps/license/views/item_report.py",
    "backend/apps/license/views/ledger.py",
    "backend/apps/license/views/ledger_upload.py",
    "backend/apps/license/models/core.py",
    "backend/apps/license/services/exporters/ledger_pdf.py",
    "backend/apps/license/services/report_service.py",
    "backend/apps/license/views/license.py",
    "backend/apps/license/tests/test_license_group_data.py",
    "backend/apps/accounts/tests.py",
    "backend/apps/accounts/views/auth.py",
    "frontend/src/context/AuthContext.tsx",
    "frontend/src/test/useAuth.test.tsx",
    "master-data-service/masters/auth.py",
    "master-data-service/masters/tests/test_api.py",
    "backend/tests/test_ledger_parser.py",
    "backend/tests/test_api_license.py",
    "backend/tests/test_authentication_query_param.py",
    "docs/audit/large-module-decomposition-plan.md",
    "frontend/package-lock.json",
    "frontend/src/pages/masters/MasterList.smoke.test.tsx",
    "frontend/src/pages/masters/MasterList.tsx",
    "frontend/src/pages/masters/MasterForm.tsx",
    "frontend/src/pages/masters/MasterForm.smoke.test.tsx",
    "frontend/src/pages/masters/masterFormHelpers.test.ts",
    "frontend/src/pages/masters/masterFormHelpers.ts",
    "frontend/src/pages/masters/tables/GenericMasterCards.tsx",
    "frontend/src/pages/TradeForm.smoke.test.tsx",
    "frontend/src/pages/TradeForm.tsx",
    "frontend/src/pages/tradeFormHelpers.test.ts",
    "frontend/src/pages/tradeFormHelpers.ts",
    "frontend/src/routes/AppRoutes.tsx",
    "frontend/src/test/setup.ts",
    "frontend/vite.config.js",
    "frontend/vitest.config.ts",
    "mds-client/tests/test_model_map.py",
    "scripts/testing/run-tests.sh",
}

BLOCKED_VERIFIED_FILES: set[str] = set()

REQUIRES_RECHECK_FILES: set[str] = set()

COMPLETED_VERIFIED_FILES.update({
    "backend/apps/allotment/scripts/allotment_pdf.py",
    "backend/apps/allotment/scripts/aro.py",
    "backend/apps/allotment/signals.py",
    "backend/apps/allotment/views_actions.py",
    "backend/apps/bill_of_entry/views/detail_update_views.py",
    "backend/apps/core/management/commands/fetch_detail_bisc.py",
    "backend/apps/core/management/commands/report_fetch.py",
    "backend/apps/core/scripts/calculate_balance.py",
    "backend/apps/core/scripts/ledger.py",
    "backend/apps/core/serializers/fields.py",
    "backend/apps/core/tests/test_mds_write_cutover.py",
    "backend/apps/core/utils/transfer_letter.py",
    "backend/apps/core/utils/validation.py",
    "backend/apps/core/views/activity_log.py",
    "backend/apps/core/views/throttle_status.py",
    "backend/apps/license/item_report.py",
    "backend/apps/license/ledger_pdf.py",
    "backend/apps/license/management/commands/parse_existing_license_copies.py",
    "backend/apps/license/parsers/dfia_pdf.py",
    "backend/apps/license/services/exporters/license_balance_pdf.py",
    "backend/apps/trade/bill_of_supply_pdf.py",
    "backend/apps/trade/purchase_invoice_pdf.py",
    "backend/scripts/test_crud_balance_updates.py",
    "backend/shared/pdf/__init__.py",
    "backend/shared/pdf/builders.py",
    "backend/tests/test_api_integration.py",
})

COMPLETED_VERIFIED_FILES.update({
    "backend/apps/accounts/__init__.py",
    "backend/apps/accounts/admin.py",
    "backend/apps/accounts/apps.py",
    "backend/apps/accounts/management/__init__.py",
    "backend/apps/accounts/management/commands/__init__.py",
    "backend/apps/accounts/management/commands/check_user_roles.py",
    "backend/apps/accounts/management/commands/migrate_auth.py",
    "backend/apps/accounts/management/commands/repair_user_fk_constraints.py",
    "backend/apps/accounts/migrations/0001_initial.py",
    "backend/apps/accounts/migrations/0002_alter_user_avatar.py",
    "backend/apps/accounts/migrations/__init__.py",
    "backend/apps/accounts/models.py",
    "backend/apps/accounts/serializers.py",
    "backend/apps/accounts/services.py",
    "backend/apps/accounts/signals.py",
    "backend/apps/accounts/tasks.py",
    "backend/apps/accounts/templates/emails/password_reset.html",
    "backend/apps/accounts/urls.py",
    "backend/apps/accounts/views/__init__.py",
    "backend/apps/accounts/views/password.py",
    "backend/apps/accounts/views/user_management.py",
    "backend/apps/license/migrations/0008_repoint_user_fk_to_accounts_user.py",
    "backend/lmanagement/settings.py",
    "backend/apps/core/templates/registration/login.html",
    "backend/templates/base/login.html",
    "backend/templates/forgot-password.html",
    "backend/templates/login.html",
    "backend/templates/registration/login.html",
    "backend/templates/registration/password_reset_done.html",
    "backend/templates/registration/password_reset_form.html",
    "backend/tests/conftest.py",
    "backend/theme/login.html",
    "frontend/src/components/AuthedImage.tsx",
    "frontend/src/pages/Login.test.tsx",
    "frontend/src/pages/Login.tsx",
    "frontend/src/pages/auth/PasswordReset.tsx",
    "frontend/src/pages/errors/Unauthorized.tsx",
    "frontend/src/utils/authRedirect.ts",
    "master-data-service/masters/tests/test_fk_serialization.py",
    "master-data-service/mds/settings.py",
    "mds-client/mds_client/client.py",
    "mds-client/mds_client/settings.py",
    "mds-client/tests/support.py",
    "mds-client/tests/test_client.py",
    "tests/e2e/conftest.py",
    "tests/e2e/test_api_smoke.py",
    "tests/e2e/test_pages_selenium.py",
})

COMPLETED_VERIFIED_FILES.update({
    "backend/apps/accounts/permissions.py",
    "backend/apps/allotment/views.py",
    "backend/apps/bill_of_entry/views/boe.py",
    "backend/apps/core/urls.py",
    "backend/apps/core/views/master_view.py",
    "backend/apps/core/views/mds_status.py",
    "backend/apps/core/views/media.py",
    "backend/apps/core/tests/test_mds_write_cutover.py",
    "backend/apps/bill_of_entry/views/parse_pdf.py",
    "backend/apps/core/views/health.py",
    "backend/apps/license/urls.py",
    "backend/apps/license/views/active_licenses_report.py",
    "backend/apps/license/views/dashboard.py",
    "backend/apps/license/views/expiring_licenses_report.py",
    "backend/apps/license/views/inventory_balance_report.py",
    "backend/apps/license/views/inventory_balance_viewset.py",
    "backend/apps/license/views/item_plan.py",
    "backend/apps/license/views/parse_pdf.py",
    "backend/apps/license/views_incentive.py",
    "backend/apps/tasks/views.py",
    "backend/apps/trade/views.py",
    "backend/lmanagement/urls.py",
    "backend/tests/test_api_core.py",
    "backend/tests/test_authorization_permissions.py",
    "docs/architecture/NAVBAR_ROLE_MAPPING.md",
    "docs/audit/phase-01-authentication-report.md",
    "docs/audit/phase-02-authorization-report.md",
    "frontend/src/components/CommandPalette.test.tsx",
    "frontend/src/components/CommandPalette.tsx",
    "frontend/src/components/PermissionGate.tsx",
    "frontend/src/components/TopNav.test.tsx",
    "frontend/src/components/TopNav.tsx",
    "frontend/src/layout/Sidebar.tsx",
    "frontend/src/pages/Dashboard.tsx",
    "frontend/src/pages/Forbidden.tsx",
    "frontend/src/routes/AppRoutes.tsx",
    "frontend/src/routes/authorizationRoles.ts",
    "frontend/src/routes/ProtectedRoute.tsx",
    "frontend/src/types/index.ts",
    "frontend/src/utils/roleConstants.js",
})

COMPLETED_VERIFIED_FILES.update({
    "docs/07-user-flows.md",
    "docs/audit/phase-03-users-report.md",
    "frontend/src/api/users.js",
    "frontend/src/pages/admin/UserForm.test.tsx",
    "frontend/src/pages/admin/UserForm.tsx",
    "frontend/src/pages/admin/UserList.test.tsx",
    "frontend/src/pages/admin/UserList.tsx",
})

COMPLETED_VERIFIED_FILES.update({
    "docs/04-api.md",
    "docs/06-business-rules.md",
    "docs/08-security.md",
    "docs/architecture/RBAC_DOCUMENTATION.md",
    "docs/audit/phase-04-roles-permissions-report.md",
    "docs/operations/RBAC_SETUP_INSTRUCTIONS.md",
})

COMPLETED_VERIFIED_FILES.update({
    "master-data-service/.env.example",
    "master-data-service/.env.production.example",
    "master-data-service/.gitignore",
    "master-data-service/README.md",
    "master-data-service/deploy/deploy-mds.sh",
    "master-data-service/deploy/gunicorn.conf.py",
    "master-data-service/deploy/mds.service",
    "master-data-service/deploy/nginx-mds.conf",
    "master-data-service/manage.py",
    "master-data-service/masters/__init__.py",
    "master-data-service/masters/admin.py",
    "master-data-service/masters/apps.py",
    "master-data-service/masters/management/__init__.py",
    "master-data-service/masters/management/commands/__init__.py",
    "master-data-service/masters/management/commands/load_masters.py",
    "master-data-service/masters/migrations/0001_initial.py",
    "master-data-service/masters/migrations/__init__.py",
    "master-data-service/masters/models.py",
    "master-data-service/masters/pagination.py",
    "master-data-service/masters/serializers.py",
    "master-data-service/masters/signals.py",
    "master-data-service/masters/tests/__init__.py",
    "master-data-service/masters/tests/test_load_masters.py",
    "master-data-service/masters/urls.py",
    "master-data-service/masters/views.py",
    "master-data-service/mds/__init__.py",
    "master-data-service/mds/asgi.py",
    "master-data-service/mds/urls.py",
    "master-data-service/mds/wsgi.py",
    "master-data-service/pytest.ini",
})

COMPLETED_VERIFIED_FILES.update({
    "mds-client/.gitignore",
    "mds-client/README.md",
    "mds-client/mds_client/__init__.py",
    "mds-client/mds_client/admin.py",
    "mds-client/mds_client/apps.py",
    "mds-client/mds_client/client.py",
    "mds-client/mds_client/keys.py",
    "mds-client/mds_client/management/__init__.py",
    "mds-client/mds_client/management/commands/__init__.py",
    "mds-client/mds_client/management/commands/mds_sync.py",
    "mds-client/mds_client/migrations/0001_initial.py",
    "mds-client/mds_client/migrations/__init__.py",
    "mds-client/mds_client/model_map.py",
    "mds-client/mds_client/models.py",
    "mds-client/mds_client/settings.py",
    "mds-client/mds_client/sync.py",
    "mds-client/mds_client/tasks.py",
    "mds-client/pyproject.toml",
    "mds-client/pytest.ini",
    "mds-client/runtests.py",
    "mds-client/tests/__init__.py",
    "mds-client/tests/conftest.py",
    "mds-client/tests/mirror_app/__init__.py",
    "mds-client/tests/mirror_app/apps.py",
    "mds-client/tests/mirror_app/models.py",
    "mds-client/tests/settings.py",
    "mds-client/tests/support.py",
    "mds-client/tests/test_client.py",
    "mds-client/tests/test_model_map.py",
    "mds-client/tests/test_sync.py",
})

COMPLETED_VERIFIED_FILES.update({
    "backend/apps/core/__init__.py",
    "backend/apps/core/MDS_SYNC.md",
    "backend/apps/core/apps.py",
    "backend/apps/core/cache_signals.py",
    "backend/apps/core/cache_utils.py",
    "backend/apps/core/cached_views.py",
    "backend/apps/core/constants.py",
    "backend/apps/core/exporters/__init__.py",
    "backend/apps/core/exporters/base.py",
    "backend/apps/core/exporters/excel/__init__.py",
    "backend/apps/core/exporters/excel/base_excel.py",
    "backend/apps/core/exporters/excel/workbook_builder.py",
    "backend/apps/core/exporters/pdf/__init__.py",
    "backend/apps/core/exporters/pdf/base_pdf.py",
    "backend/apps/core/exporters/pdf/styles.py",
    "backend/apps/core/exporters/pdf/table_builder.py",
    "backend/apps/core/filters.py",
    "backend/apps/core/filtersets.py",
    "backend/apps/core/helpers.py",
    "backend/apps/core/management/__init__.py",
    "backend/apps/core/management/commands/__init__.py",
    "backend/apps/core/management/commands/_item_linking.py",
    "backend/apps/core/management/commands/audit_database_integrity.py",
    "backend/apps/core/management/commands/audit_masters.py",
    "backend/apps/core/management/commands/auto_import_masters.py",
    "backend/apps/core/management/commands/cache_stats.py",
    "backend/apps/core/management/commands/check_db_structure.py",
    "backend/apps/core/management/commands/check_master_quality.py",
    "backend/apps/core/management/commands/clean_duplicate_rowdetails.py",
    "backend/apps/core/management/commands/clean_item_names.py",
    "backend/apps/core/management/commands/clearcache.py",
    "backend/apps/core/management/commands/convert_docx_to_pdf.py",
    "backend/apps/core/management/commands/convert_license_table.py",
    "backend/apps/core/management/commands/diff_masters.py",
    "backend/apps/core/management/commands/export_masters_mds.py",
    "backend/apps/core/management/commands/fetch_detail_conf.py",
    "backend/apps/core/management/commands/fetch_exchange_rates.py",
    "backend/apps/core/management/commands/merge_masters.py",
    "backend/apps/core/management/commands/rebuild_migrations.py",
    "backend/apps/core/management/commands/reconcile_masters.py",
    "backend/apps/core/management/commands/refresh_materialized_views.py",
    "backend/apps/core/management/commands/reset_migration_history.py",
    "backend/apps/core/management/commands/rqworker.py",
    "backend/apps/core/management/commands/seed_e132_plan_items.py",
    "backend/apps/core/management/commands/sync_database_schema.py",
    "backend/apps/core/management/commands/update_aluminium_foil_items.py",
    "backend/apps/core/management/commands/update_dgft_descriptions.py",
    "backend/apps/core/management/commands/update_sugar_items.py",
    "backend/apps/core/management/commands/validate_db_fields.py",
    "backend/apps/core/materialized_views.py",
    "backend/apps/core/migrations/0001_initial.py",
    "backend/apps/core/migrations/0002_remove_companymodel_address.py",
    "backend/apps/core/migrations/0003_create_materialized_views.py",
    "backend/apps/core/migrations/0004_headsionnormsmodel_created_on_and_more.py",
    "backend/apps/core/migrations/0005_add_uid_to_keyless_masters.py",
    "backend/apps/core/migrations/0006_backfill_master_uids.py",
    "backend/apps/core/migrations/0007_seed_e132_plan_items.py",
    "backend/apps/core/migrations/0008_seed_e132_extra_plan_items.py",
    "backend/apps/core/migrations/0009_seed_e132_cmc_plan_item.py",
    "backend/apps/core/migrations/0010_sync_e132_display_order.py",
    "backend/apps/core/migrations/0011_split_milk_into_swp_dwp_wpc.py",
    "backend/apps/core/migrations/__init__.py",
    "backend/apps/core/mds_payload.py",
    "backend/apps/core/mds_write.py",
    "backend/apps/core/models.py",
    "backend/apps/core/pagination.py",
    "backend/apps/core/scripts/__init__.py",
    "backend/apps/core/serializers/__init__.py",
    "backend/apps/core/serializers/mixins.py",
    "backend/apps/core/serializers/models.py",
    "backend/apps/core/signals_materialized_views.py",
    "backend/apps/core/templatetags/__init__.py",
    "backend/apps/core/templatetags/core_tag.py",
    "backend/apps/core/templates/base.html",
    "backend/apps/core/templates/core/add.html",
    "backend/apps/core/templates/core/ledger.html",
    "backend/apps/core/templates/core/list.html",
    "backend/apps/core/templates/core/message.html",
    "backend/apps/core/templates/dashboard.html",
    "backend/apps/core/templates/pdf_base.html",
    "backend/apps/core/templates/sion/detail.html",
    "backend/apps/core/templates/upload.html",
    "backend/apps/core/templates/widgets/multiwidget.html",
    "backend/apps/core/tasks.py",
    "backend/apps/core/tasks_materialized_views.py",
    "backend/apps/core/tests/test_cache_signals.py",
    "backend/apps/core/tests/test_cache_utils.py",
    "backend/apps/core/tests/__init__.py",
    "backend/apps/core/tests/test_check_master_quality.py",
    "backend/apps/core/tests/test_date_utils.py",
    "backend/apps/core/tests/test_decimal_utils.py",
    "backend/apps/core/tests/test_keyless_uid.py",
    "backend/apps/core/tests/test_materialized_views.py",
    "backend/apps/core/tests/test_reconcile_masters.py",
    "backend/apps/core/tests/test_validation.py",
    "backend/apps/core/throttling.py",
    "backend/apps/core/utils/__init__.py",
    "backend/apps/core/utils/date_utils.py",
    "backend/apps/core/utils/decimal_utils.py",
    "backend/apps/core/utils/exceptions.py",
    "backend/apps/core/utils/pdf_helpers.py",
    "backend/apps/core/utils/pdf_utils.py",
    "backend/apps/core/views/__init__.py",
    "backend/apps/core/views/views.py",
    "frontend/src/pages/masters/BoeMergeModal.tsx",
    "frontend/src/pages/masters/BoeParsePanel.tsx",
    "frontend/src/pages/masters/LicenseParsePanel.tsx",
    "frontend/src/pages/masters/LinkTradeModal.tsx",
    "frontend/src/pages/masters/NestedFieldArray.tsx",
    "frontend/src/pages/masters/TradeMetaBadges.tsx",
    "frontend/src/pages/masters/entitySections.ts",
    "frontend/src/pages/masters/masterDisplayFormatters.test.ts",
    "frontend/src/pages/masters/masterDisplayFormatters.ts",
    "frontend/src/pages/masters/masterListConfig.test.ts",
    "frontend/src/pages/masters/masterListConfig.ts",
    "frontend/src/pages/masters/tables/AllotmentsTable.tsx",
    "frontend/src/pages/masters/tables/IncentiveLicensesTable.tsx",
    "frontend/src/services/api/masterApi.js",
    "backend/scripts/golden_master_balance_exporters.py",
    "backend/scripts/golden_master_ledger_pdf.py",
    "backend/tests/test_export_masters_mds.py",
    "scripts/maintenance/_master_sync_lib.sh",
    "scripts/maintenance/apply-master-merge.sh",
    "scripts/maintenance/audit-and-diff-masters.sh",
    "scripts/maintenance/audit-and-merge-masters.sh",
    "scripts/maintenance/sync-masters.sh",
    "scripts/mds/_lib.sh",
    "scripts/mds/export-master-data.sh",
    "scripts/mds/load-master-data.sh",
    "scripts/mds/migrate-all-servers.sh",
    "scripts/mds/onboard-server.sh",
    "docs/architecture/ADR-001-master-data-service.md",
    "docs/architecture/MODULARIZATION_MASTER_PLAN.md",
    "docs/operations/master-consolidation.md",
})

COMPLETED_VERIFIED_FILES.update({
    "backend/apps/allotment/scripts/pdf_coordinate_finder.py",
    "backend/apps/allotment/views_export.py",
    "backend/apps/bill_of_entry/views/__init__.py",
    "backend/apps/bill_of_entry/views_export.py",
    "backend/tests/test_pdf_coordinate_finder.py",
    "backend/tests/test_api_allotment.py",
    "backend/tests/test_api_boe.py",
    "docs/README.md",
    "docs/guides/PDF_VIEWER_IMPLEMENTATION.md",
    "docs/audit/phase-07-reporting-report.md",
    "frontend/src/components/reports/LicenseExportPanel.test.tsx",
    "frontend/src/components/reports/LicenseExportPanel.tsx",
    "frontend/src/pages/reports/ActiveLicenses.test.tsx",
    "frontend/src/pages/reports/ActiveLicenses.tsx",
    "frontend/src/pages/reports/DownloadLicense.test.tsx",
    "frontend/src/pages/reports/DownloadLicense.tsx",
    "frontend/src/pages/reports/ExpiringLicenses.test.tsx",
    "frontend/src/pages/reports/ExpiringLicenses.tsx",
    "frontend/src/pages/reports/ItemPivotFilters.test.tsx",
    "frontend/src/pages/reports/ItemPivotFilters.tsx",
    "frontend/src/pages/reports/ItemPivotReport.test.ts",
    "frontend/src/pages/reports/ItemPivotReport.tsx",
    "frontend/src/pages/reports/ItemReport.test.ts",
    "frontend/src/pages/reports/ItemReport.tsx",
    "frontend/src/pages/reports/NormCardGrid.test.tsx",
    "frontend/src/pages/reports/NormCardGrid.tsx",
    "frontend/src/pages/reports/SionE1.test.tsx",
    "frontend/src/pages/reports/SionE1.tsx",
    "frontend/src/pages/reports/SionE126.test.tsx",
    "frontend/src/pages/reports/SionE126.tsx",
    "frontend/src/pages/reports/SionE132.test.tsx",
    "frontend/src/pages/reports/SionE132.tsx",
    "frontend/src/pages/reports/SionE5.test.tsx",
    "frontend/src/pages/reports/SionE5.tsx",
    "frontend/src/pages/reports/SionNormReport.test.tsx",
    "frontend/src/pages/reports/SionNormReport.tsx",
    "frontend/src/pages/PDFViewer.test.tsx",
    "frontend/src/pages/PDFViewer.tsx",
    "frontend/src/utils/documentDownload.test.ts",
    "frontend/src/utils/documentDownload.ts",
    "frontend/src/utils/pdfPreview.js",
    "frontend/src/utils/pdfPreview.test.ts",
    "backend/apps/license/models/invoice.py",
    "backend/apps/license/services/exporters/license_balance_excel.py",
    "backend/apps/license/tables.py",
    "backend/apps/license/helper.py",
    "backend/apps/license/management/__init__.py",
    "backend/apps/license/management/commands/__init__.py",
    "backend/apps/license/management/commands/delete_licenses_by_exporter.py",
    "backend/apps/license/management/commands/migrate_purchase_status_np_to_mi.py",
    "backend/apps/license/management/commands/populate_license_items.py",
    "backend/apps/license/management/commands/repair_license_subtables.py",
    "backend/apps/license/management/commands/resync_local_to_server.py",
    "backend/apps/license/management/commands/sync_licenses.py",
    "backend/apps/license/management/commands/update_balance_cif.py",
    "backend/apps/license/management/commands/update_license_expiry.py",
    "backend/apps/license/management/commands/upload_dfia_copies.py",
    "backend/apps/license/tests/test_balance_calculator.py",
    "backend/apps/license/tests/__init__.py",
    "backend/apps/license/tests/test_delete_licenses_by_exporter_command.py",
    "backend/apps/license/tests/test_e132_plan.py",
    "backend/apps/license/tests/test_e1_plan.py",
    "backend/apps/license/tests/test_e5_plan.py",
    "backend/apps/license/tests/test_invoice_models.py",
    "backend/apps/license/tests/test_item_matcher.py",
    "backend/apps/license/tests/test_license_items_view.py",
    "backend/apps/license/tests/test_license_report_view.py",
    "backend/apps/license/tests/test_populate_license_items_command.py",
    "backend/apps/license/tests/test_query_builder.py",
    "backend/apps/license/tests/test_repair_license_subtables_command.py",
    "backend/apps/license/tests/test_resync_local_to_server_command.py",
    "backend/apps/license/tests/test_sync_licenses_command.py",
    "backend/apps/license/tests/test_update_balance_cif_command.py",
    "backend/apps/license/tests/test_update_license_expiry_command.py",
    "backend/apps/license/tests/test_upload_dfia_copies_command.py",
    "backend/apps/license/tests/test_migrate_purchase_status_command.py",
    "backend/apps/license/tests/test_tables.py",
    "backend/apps/license/utils/query_builder.py",
    "backend/tests/test_api_license.py",
    "backend/apps/license/migrations/0001_initial.py",
    "backend/apps/license/migrations/0002_scheme_and_notification_to_fk.py",
    "backend/apps/license/migrations/0003_remove_licensedetailsmodel_license_lic_notific_5b1519_idx_and_more.py",
    "backend/apps/license/migrations/0004_licensedetailsmodel_archived_exporter_name_and_more.py",
    "backend/apps/license/migrations/0005_licensebalance_licenseflags_licensenotes_and_more.py",
    "backend/apps/license/migrations/0006_drop_obsolete_scheme_notification_columns.py",
    "backend/apps/license/migrations/0007_drop_obsolete_subtable_columns.py",
    "backend/apps/license/migrations/0009_licenseitemplan.py",
    "backend/apps/license/migrations/0010_licenseitemplan_item_name_licenseitemplan_unit_price_and_more.py",
    "backend/apps/license/migrations/0011_harden_invoice_validation.py",
    "backend/apps/license/migrations/0012_enforce_invoice_non_negative_constraints.py",
    "backend/apps/license/migrations/__init__.py",
    "backend/apps/license/parsers/__init__.py",
    "backend/apps/license/serializers/_license_write.py",
    "backend/apps/license/serializers/incentive.py",
    "backend/apps/license/services/balance_calculator.py",
    "backend/apps/license/services/dgft_ownership.py",
    "backend/apps/license/services/e132_plan.py",
    "backend/apps/license/services/ledger_service.py",
    "backend/apps/license/services/plan_enforcement.py",
    "backend/apps/license/services/plan_grouping.py",
    "backend/apps/license/services/validation_service.py",
    "backend/apps/license/signals.py",
    "backend/apps/license/table_columns.py",
    "backend/apps/license/templates/license/add.html",
    "backend/apps/license/templates/license/consolidated.html",
    "backend/apps/license/templates/license/detail.html",
    "backend/apps/license/tests/test_dgft_ownership.py",
    "backend/apps/license/tests/test_incentive_serializers.py",
    "backend/apps/license/tests/test_ledger_service.py",
    "backend/apps/license/tests/test_plan_enforcement.py",
    "backend/apps/license/tests/test_plan_grouping.py",
    "backend/apps/license/tests/test_signals.py",
    "backend/apps/license/tests/test_table_columns.py",
    "backend/apps/license/tests/test_validation_service.py",
    "backend/apps/license/utils/item_matcher.py",
    "backend/apps/license/views/license_items.py",
    "backend/apps/license/views/license_report.py",
    "docs/audit/phase-06-license-report.md",
})

VERIFICATION_HISTORY = [
    "Phase 1 remaining backend authentication recheck: .venv/bin/python -m pytest backend/apps/accounts/tests.py backend/tests/test_authentication_query_param.py backend/tests/test_all_conditions.py::TestAuthentication backend/tests/test_ledger_parser.py -q -> 28 passed",
    "Phase 1 remaining backend authentication Ruff: .venv/bin/ruff check backend/apps/accounts backend/apps/core/throttling.py backend/lmanagement/settings.py backend/apps/core/middleware.py backend/apps/core/authentication.py backend/tests/test_all_conditions.py backend/tests/test_authentication_query_param.py --select F821,F811,E741,F841,F401 -> clean",
    "Phase 1 final frontend authentication tests: npm test -- --run src/pages/Login.test.tsx src/test/useAuth.test.tsx -> 13 passed",
    "Phase 1 final frontend authentication typecheck: npm run typecheck -> passed",
    "Phase 1 final frontend authentication lint: npm run lint -> passed",
    "Phase 2 focused authorization regression: .venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_authentication_query_param.py backend/tests/test_api_license.py -q -> 15 passed",
    "Phase 2 targeted backend authorization Ruff: .venv/bin/ruff check backend/apps/accounts/permissions.py backend/apps/license/views_actions.py backend/tests/test_authorization_permissions.py --select F821,F811,E741,F841,F401 -> clean",
    "Phase 2 frontend authorization typecheck: npm run typecheck -> passed",
    "Phase 2 frontend authorization lint: npm run lint -> passed",
    "Phase 2 master-data authorization regression: .venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/apps/core/tests/test_mds_write_cutover.py backend/tests/test_api_core.py -q -> 23 passed",
    "Phase 2 master-data authorization Ruff: .venv/bin/ruff check backend/apps/core/views/master_view.py backend/tests/test_authorization_permissions.py backend/apps/core/tests/test_mds_write_cutover.py --select F821,F811,E741,F841,F401 -> clean",
    "Phase 2 frontend navigation authorization regression: npm test -- --run src/components/TopNav.test.tsx -> 1 passed",
    "Phase 2 frontend authorization typecheck after route-role consolidation: npm run typecheck -> passed",
    "Phase 2 frontend authorization lint after route-role consolidation: npm run lint -> passed",
    "Phase 2 frontend dependency security audit: npm audit --audit-level=high -> 0 vulnerabilities",
    "Phase 2 Python dependency security audit: pip-audit not installed in the local environment",
    "Phase 2 domain authorization regression: .venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_allotment.py backend/tests/test_api_boe.py backend/tests/test_api_core.py -q -> 26 passed",
    "Phase 2 domain authorization Ruff: .venv/bin/ruff check backend/apps/allotment/views.py backend/apps/bill_of_entry/views/boe.py backend/apps/core/urls.py backend/apps/tasks/views.py backend/apps/core/views/mds_status.py backend/apps/core/views/media.py backend/apps/license/views/dashboard.py --select F821,F811,E741,F841,F401 -> clean",
    "Phase 2 BOE parser authorization regression: .venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_boe.py -q -> 12 passed",
    "Phase 2 BOE parser authorization Ruff: .venv/bin/ruff check backend/apps/bill_of_entry/views/parse_pdf.py backend/tests/test_authorization_permissions.py --select F821,F811,E741,F841,F401 -> clean",
    "Phase 2 non-Trade permission cleanup tests: .venv/bin/python -m pytest backend/tests/test_api_license.py backend/apps/license/tests/test_license_group_data.py -q -> 12 passed",
    "Phase 2 non-Trade permission cleanup Ruff: .venv/bin/ruff check backend/apps/license/views/parse_pdf.py backend/apps/license/views/item_plan.py backend/apps/license/views_incentive.py backend/apps/license/views/inventory_balance_viewset.py backend/apps/core/views/health.py --select F821,F811,E741,F841,F401 -> clean",
    "Phase 2 direct report authorization regression: .venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_license.py backend/apps/license/tests/test_license_group_data.py -q -> 20 passed",
    "Phase 2 direct report authorization Ruff: .venv/bin/ruff check backend/apps/license/views/active_licenses_report.py backend/apps/license/views/expiring_licenses_report.py backend/apps/license/views/inventory_balance_report.py backend/apps/license/views/item_pivot_report.py backend/apps/license/views/item_report.py backend/tests/test_authorization_permissions.py --select F401,F821,F811,E741,F841 -> clean",
    "Phase 2 constrained Trade authorization regression: .venv/bin/python -m pytest backend/tests/test_authorization_permissions.py backend/tests/test_api_trade.py -q -> 19 passed",
    "Phase 2 constrained Trade authorization Ruff: .venv/bin/ruff check backend/apps/trade/views.py backend/tests/test_authorization_permissions.py --select F401,F821,F811,E741,F841 -> clean",
    "Phase 2 frontend command/dashboard authorization tests: npm test -- --run src/components/CommandPalette.test.tsx src/components/TopNav.test.tsx -> 4 passed",
    "Phase 2 frontend command/dashboard typecheck: npm run typecheck -> passed",
    "Phase 2 frontend command/dashboard lint: npm run lint -> passed",
    "Phase 2 frontend command/dashboard dependency security audit: npm audit --audit-level=high -> 0 vulnerabilities",
    "Focused backend account tests after admin password validation and migrate_auth fixes: .venv/bin/python -m pytest backend/apps/accounts/tests.py -q -> 7 passed",
    "Targeted backend auth management Ruff: .venv/bin/ruff check backend/apps/accounts/tests.py backend/apps/accounts/management/commands/migrate_auth.py backend/apps/accounts/management/commands/check_user_roles.py backend/apps/accounts/serializers.py backend/apps/accounts/views/user_management.py --select F821,F811,E741,F841,F401 -> clean",
    "Focused frontend login auth tests: npm test -- --run src/pages/Login.test.tsx -> 2 passed",
    "Frontend typecheck after login/reset routing: npm run typecheck -> passed",
    "Frontend lint after login/reset routing: npm run lint -> passed",
    "Focused MDS auth/config tests: ../.venv/bin/python -m pytest masters/tests/test_api.py::TestAuth masters/tests/test_fk_serialization.py -q -> 9 passed",
    "Focused mds-client auth/config tests: ../.venv/bin/python -m pytest tests/test_client.py -q -> 15 passed",
    "Targeted MDS auth/config Ruff: ../.venv/bin/ruff check masters/auth.py masters/tests/test_api.py masters/tests/test_fk_serialization.py mds/settings.py --select F821,F811,E741,F841,F401 -> clean",
    "Targeted mds-client auth/config Ruff: ../.venv/bin/ruff check mds_client/client.py mds_client/settings.py tests/test_client.py tests/support.py --select F821,F811,E741,F841,F401 -> clean",
    "E2E API auth smoke tests: .venv/bin/python -m pytest tests/e2e/test_api_smoke.py::test_login_returns_token tests/e2e/test_api_smoke.py::test_login_no_redirect_in_dev -q -> 2 passed",
    "E2E Selenium auth smoke module: .venv/bin/python -m pytest tests/e2e/test_pages_selenium.py -q -> skipped because selenium is not installed in this environment",
    "Targeted e2e auth Ruff: .venv/bin/ruff check tests/e2e/conftest.py tests/e2e/test_api_smoke.py tests/e2e/test_pages_selenium.py --select F821,F811,E741,F841,F401 -> clean",
    "Focused backend authentication API tests: .venv/bin/python -m pytest backend/apps/accounts/tests.py backend/tests/test_authentication_query_param.py backend/tests/test_all_conditions.py::TestAuthentication -q -> 16 passed",
    "Targeted backend authentication Ruff: .venv/bin/ruff check backend/apps/accounts/views/auth.py backend/apps/accounts/tests.py backend/apps/core/authentication.py backend/tests/test_authentication_query_param.py --select F821,F811,E741,F841,F401 -> clean",
    "Focused MDS authentication tests: ../.venv/bin/python -m pytest masters/tests/test_api.py::TestAuth -q -> 5 passed",
    "Targeted MDS authentication Ruff: ../.venv/bin/ruff check masters/auth.py masters/tests/test_api.py --select F821,F811,E741,F841,F401 -> clean",
    "Focused frontend AuthContext tests: npm test -- --run src/test/useAuth.test.tsx -> 11 passed",
    "Frontend typecheck after AuthContext hardening: npm run typecheck -> passed",
    "Frontend lint after AuthContext hardening: npm run lint -> passed",
    "Frontend TradeForm smoke coverage: npm test -- --run src/pages/TradeForm.smoke.test.tsx -> 2 passed",
    "Frontend unit tests after TradeForm smoke coverage: npm test -- --run -> 56 passed",
    "Frontend typecheck after TradeForm smoke coverage: npm run typecheck -> passed",
    "Frontend lint after TradeForm smoke coverage: npm run lint -> passed",
    "Frontend TradeForm helper focused tests: npm test -- --run src/pages/tradeFormHelpers.test.ts src/pages/TradeForm.smoke.test.tsx -> 7 passed",
    "Frontend unit tests after TradeForm payload helper extraction: npm test -- --run -> 61 passed",
    "Frontend typecheck after TradeForm payload helper extraction: npm run typecheck -> passed",
    "Frontend lint after TradeForm payload helper extraction: npm run lint -> passed",
    "Frontend MasterForm API helper focused tests: npm test -- --run src/pages/masters/masterFormHelpers.test.ts src/pages/masters/MasterForm.smoke.test.tsx -> 10 passed",
    "Frontend unit tests after MasterForm API helper extraction: npm test -- --run -> 54 passed",
    "Frontend typecheck after MasterForm API helper extraction: npm run typecheck -> passed",
    "Frontend lint after MasterForm API helper extraction: npm run lint -> passed",
    "Frontend MasterList generic card extraction smoke coverage: npm test -- --run src/pages/masters/MasterList.smoke.test.tsx -> 5 passed",
    "Frontend unit tests after GenericMasterCards extraction: npm test -- --run -> 46 passed",
    "Frontend typecheck after GenericMasterCards extraction: npm run typecheck -> passed",
    "Frontend lint after GenericMasterCards extraction: npm run lint -> passed",
    "Frontend MasterForm smoke coverage: npm test -- --run src/pages/masters/MasterForm.smoke.test.tsx -> 2 passed",
    "Frontend unit tests after MasterForm smoke coverage: npm test -- --run -> 45 passed",
    "Frontend typecheck after MasterForm smoke coverage: npm run typecheck -> passed",
    "Frontend lint after MasterForm smoke coverage: npm run lint -> passed",
    "Backend fast suite after Excel coverage: ./scripts/testing/run-tests.sh --fast -> 171 passed",
    "Focused license Excel coverage: .venv/bin/python -m pytest backend/tests/test_api_license.py -q -> 11 passed",
    "Targeted license API Ruff: .venv/bin/ruff check backend/tests/test_api_license.py --select F821,F811,E741,F841 -> clean",
    "Frontend unit tests after bundle split: npm test -- --run -> 43 passed",
    "Frontend typecheck after bundle split: npm run typecheck -> passed",
    "Frontend lint after bundle split: npm run lint -> passed",
    "Frontend build after bundle split: npm run build -> startup preloads reduced from route-wide app-components to shell/vendor chunks; Excel/PDF chunks no longer preloaded by index.html",
    "Backend fast suite after CSRF/upload hardening: ./scripts/testing/run-tests.sh --fast -> 169 passed",
    "Focused upload/auth regressions: .venv/bin/python -m pytest backend/tests/test_ledger_parser.py backend/tests/test_authentication_query_param.py -q -> 9 passed",
    "Targeted upload CSRF Ruff: .venv/bin/ruff check backend/apps/core/middleware.py backend/apps/license/views/ledger_upload.py backend/tests/test_ledger_parser.py --select F821,F811,E741,F841 -> clean",
    "Focused auth regressions: .venv/bin/python -m pytest backend/tests/test_authentication_query_param.py backend/tests/test_all_conditions.py::TestAuthentication -q -> 13 passed",
    "Targeted auth Ruff: .venv/bin/ruff check backend/apps/core/authentication.py backend/tests/test_authentication_query_param.py --select F821,F811,E741,F841 -> clean",
    "Targeted Ruff: .venv/bin/ruff check backend mds-client master-data-service scripts tests --select F841 -> clean",
    "Backend fast suite after F841 pass: ./scripts/testing/run-tests.sh --fast -> 164 passed",
    "Targeted Ruff: .venv/bin/ruff check backend mds-client master-data-service scripts tests --select F811,E741 -> clean",
    "Focused backend regressions: .venv/bin/python -m pytest backend/tests/test_api_boe.py backend/tests/test_api_license.py backend/apps/license/tests/test_license_group_data.py -q -> 17 passed",
    "Syntax check: python3 -m py_compile on F811/E741-touched modules -> passed",
    "Focused license API regression: .venv/bin/python -m pytest backend/tests/test_api_license.py -q -> 9 passed",
    "Syntax check: python3 -m py_compile backend/apps/core/management/commands/sync_from_ge_server.py backend/apps/license/views_actions.py docs/audit/build_audit_state.py -> passed",
    "Backend fast suite: ./scripts/testing/run-tests.sh --fast -> 163 passed",
    "Frontend lint: npm run lint -> passed",
    "Frontend typecheck: npm run typecheck -> passed",
    "Frontend unit tests: npm test -- --run -> 43 passed",
    "Frontend dependency audit: npm audit --audit-level=high -> 0 vulnerabilities",
    "Frontend build: npm run build -> passed",
    "MDS client tests: ../.venv/bin/python -m pytest tests -q -> 30 passed",
    "Master data service tests: ../.venv/bin/python -m pytest masters/tests -q -> 22 passed",
    "Phase 3 frontend Users regression: npm test -- --run src/pages/admin/UserForm.test.tsx src/pages/admin/UserList.test.tsx -> 3 passed",
    "Phase 3 frontend Users typecheck: npm run typecheck -> passed",
    "Phase 3 frontend Users lint: npm run lint -> passed",
    "Phase 3 backend Users/accounts regression: .venv/bin/python -m pytest backend/apps/accounts/tests.py -q -> 9 passed",
    "Phase 3 targeted Users Ruff: .venv/bin/ruff check backend/apps/accounts/tests.py backend/apps/accounts/serializers.py backend/apps/accounts/views/user_management.py --select F401,F821,F811,E741,F841 -> clean",
    "Phase 3 frontend Users dependency security audit: npm audit --audit-level=high -> 0 vulnerabilities",
    "Phase 4 RBAC documentation stale-reference scan: rg api/accounts, role_ids, reset_password, available_roles, custom Role references in RBAC/API/security docs -> clean except intentional get_role_codes helper references",
    "Phase 5 MDS package tests: ../.venv/bin/python -m pytest masters/tests -q -> 25 passed",
    "Phase 5 MDS targeted Ruff: ../.venv/bin/ruff check masters/views.py masters/signals.py masters/management/commands/load_masters.py masters/tests --select F401,F821,F811,E741,F841,S324 -> clean",
    "Phase 5 MDS deploy script syntax: bash -n deploy/deploy-mds.sh -> passed",
    "Phase 5 MDS Python compile: ../.venv/bin/python -m py_compile manage.py mds/asgi.py mds/wsgi.py mds/urls.py mds/settings.py masters/admin.py masters/apps.py masters/models.py masters/pagination.py masters/serializers.py masters/signals.py masters/urls.py masters/views.py masters/management/commands/load_masters.py -> passed",
    "Phase 5 mds-client tests: ../.venv/bin/python -m pytest tests -q -> 32 passed",
    "Phase 5 mds-client targeted Ruff: ../.venv/bin/ruff check mds_client tests runtests.py --select F401,F821,F811,E741,F841 -> clean",
    "Phase 5 mds-client Python compile: ../.venv/bin/python -m py_compile runtests.py mds_client/__init__.py mds_client/admin.py mds_client/apps.py mds_client/client.py mds_client/keys.py mds_client/management/commands/mds_sync.py mds_client/model_map.py mds_client/models.py mds_client/settings.py mds_client/sync.py mds_client/tasks.py tests/conftest.py tests/settings.py tests/mirror_app/apps.py tests/mirror_app/models.py tests/test_sync.py -> passed",
    "Phase 5 backend core scaffolding Ruff: .venv/bin/ruff check backend/apps/core/__init__.py backend/apps/core/apps.py backend/apps/core/constants.py backend/apps/core/serializers/__init__.py --select F401,F821,F811,E741,F841 -> clean",
    "Phase 5 backend core scaffolding compile: .venv/bin/python -m py_compile backend/apps/core/__init__.py backend/apps/core/apps.py backend/apps/core/constants.py backend/apps/core/serializers/__init__.py -> passed",
    "Phase 5 backend core models Ruff: .venv/bin/ruff check backend/apps/core/models.py --select F401,F821,F811,E741,F841 -> clean",
    "Phase 5 backend core models compile: .venv/bin/python -m py_compile backend/apps/core/models.py -> passed",
    "Phase 5 backend core models migrations check: ../.venv/bin/python manage.py makemigrations core --check --dry-run -> no changes detected; DB connection warning only",
    "Phase 5 backend core models regression: .venv/bin/python -m pytest backend/apps/core/tests/test_keyless_uid.py backend/apps/core/tests/test_mds_write_cutover.py backend/tests/test_export_masters_mds.py -q -> 25 passed",
    "Phase 5 backend core models dependency audit: .venv/bin/python -m pip_audit -r backend/requirements.txt -> blocked; pip_audit is not installed",
    "Phase 5 backend core Managers/QuerySets search: rg Manager/QuerySet/objects/as_manager in backend/apps/core -> no custom managers or querysets found",
    "Phase 5 backend core serializers Ruff: .venv/bin/ruff check backend/apps/core/serializers/models.py backend/apps/core/serializers/mixins.py --select F401,F821,F811,E741,F841,UP035,UP006 -> clean",
    "Phase 5 backend core serializers compile: .venv/bin/python -m py_compile backend/apps/core/serializers/models.py backend/apps/core/serializers/mixins.py -> passed",
    "Phase 5 backend core serializers regression: .venv/bin/python -m pytest backend/tests/test_api_core.py backend/apps/core/tests/test_mds_write_cutover.py -q -> 20 passed",
    "Phase 5 backend core services Ruff: .venv/bin/ruff check backend/apps/core/mds_payload.py backend/apps/core/mds_write.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045 -> clean",
    "Phase 5 backend core services compile: .venv/bin/python -m py_compile backend/apps/core/mds_payload.py backend/apps/core/mds_write.py -> passed",
    "Phase 5 backend core services regression: .venv/bin/python -m pytest backend/apps/core/tests/test_mds_write_cutover.py backend/tests/test_export_masters_mds.py -q -> 20 passed",
    "Phase 5 backend core ViewSets Ruff: .venv/bin/ruff check backend/apps/core/views/views.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045 -> clean",
    "Phase 5 backend core ViewSets compile: .venv/bin/python -m py_compile backend/apps/core/views/views.py -> passed",
    "Phase 5 backend core ViewSets regression: .venv/bin/python -m pytest backend/tests/test_api_core.py backend/apps/core/tests/test_mds_write_cutover.py backend/tests/test_url_routing.py -q -> 34 passed",
    "Phase 5 backend core Views Ruff: .venv/bin/ruff check backend/apps/core/views/__init__.py backend/apps/core/views/views.py --select F401,F821,F811,E741,F841 -> clean",
    "Phase 5 backend core Views compile: .venv/bin/python -m py_compile backend/apps/core/views/__init__.py backend/apps/core/views/views.py -> passed",
    "Phase 5 backend core Views regression: .venv/bin/python -m pytest backend/tests/test_url_routing.py backend/tests/test_api_core.py -q -> 23 passed",
    "Phase 5 backend core Signals Ruff: .venv/bin/ruff check backend/apps/core/signals_materialized_views.py backend/apps/core/cache_signals.py backend/apps/core/tests/test_cache_signals.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core Signals compile: .venv/bin/python -m py_compile backend/apps/core/signals_materialized_views.py backend/apps/core/cache_signals.py backend/apps/core/tests/test_cache_signals.py -> passed",
    "Phase 5 backend core Signals regression: ../.venv/bin/python -m pytest apps/core/tests/test_cache_signals.py apps/core/tests/test_mds_write_cutover.py -q -> 12 passed",
    "Phase 5 backend core Cache Ruff: .venv/bin/ruff check backend/apps/core/cache_utils.py backend/apps/core/cached_views.py backend/apps/core/tests/test_cache_utils.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,S324,B904,B007 -> clean",
    "Phase 5 backend core Cache compile: .venv/bin/python -m py_compile backend/apps/core/cache_utils.py backend/apps/core/cached_views.py backend/apps/core/tests/test_cache_utils.py -> passed",
    "Phase 5 backend core Cache regression: ../.venv/bin/python -m pytest apps/core/tests/test_cache_utils.py apps/core/tests/test_cache_signals.py -q -> 5 passed",
    "Phase 5 backend core Middleware Ruff: .venv/bin/ruff check backend/apps/core/middleware.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core Middleware compile: .venv/bin/python -m py_compile backend/apps/core/middleware.py -> passed",
    "Phase 5 backend core Middleware regression: ../.venv/bin/python -m pytest tests/test_authentication_query_param.py -q -> 3 passed",
    "Phase 5 backend core Utilities date/decimal Ruff: .venv/bin/ruff check backend/apps/core/utils/date_utils.py backend/apps/core/utils/decimal_utils.py backend/apps/core/utils/exceptions.py backend/apps/core/utils/__init__.py backend/apps/core/tests/test_date_utils.py backend/apps/core/tests/test_decimal_utils.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core Utilities date/decimal compile: .venv/bin/python -m py_compile backend/apps/core/utils/date_utils.py backend/apps/core/utils/decimal_utils.py backend/apps/core/utils/exceptions.py backend/apps/core/utils/__init__.py backend/apps/core/tests/test_date_utils.py backend/apps/core/tests/test_decimal_utils.py -> passed",
    "Phase 5 backend core Utilities date/decimal regression: ../.venv/bin/python -m pytest apps/core/tests/test_date_utils.py apps/core/tests/test_decimal_utils.py -q -> 110 passed",
    "Phase 5 backend core Utilities filter/pagination/throttling Ruff: .venv/bin/ruff check backend/apps/core/filters.py backend/apps/core/filtersets.py backend/apps/core/pagination.py backend/apps/core/throttling.py backend/apps/core/helpers.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core Utilities filter/pagination/throttling compile: .venv/bin/python -m py_compile backend/apps/core/filters.py backend/apps/core/filtersets.py backend/apps/core/pagination.py backend/apps/core/throttling.py backend/apps/core/helpers.py -> passed",
    "Phase 5 backend core Utilities filter/pagination/throttling regression: ../.venv/bin/python -m pytest tests/test_api_core.py tests/test_api_license.py tests/test_api_boe.py apps/core/tests/test_mds_write_cutover.py -q -> 38 passed",
    "Phase 5 backend core Utilities PDF Ruff: .venv/bin/ruff check backend/apps/core/utils/pdf_helpers.py backend/apps/core/utils/pdf_utils.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core Utilities PDF compile: .venv/bin/python -m py_compile backend/apps/core/utils/pdf_helpers.py backend/apps/core/utils/pdf_utils.py -> passed",
    "Phase 5 backend core Utilities PDF regression: ../.venv/bin/python -m pytest tests/test_api_boe.py tests/test_api_license.py tests/test_api_allotment.py -q -> 25 passed",
    "Phase 5 backend core Exporters Ruff: .venv/bin/ruff check backend/apps/core/exporters --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core Exporters compile: .venv/bin/python -m py_compile backend/apps/core/exporters/__init__.py backend/apps/core/exporters/base.py backend/apps/core/exporters/excel/__init__.py backend/apps/core/exporters/excel/base_excel.py backend/apps/core/exporters/excel/workbook_builder.py backend/apps/core/exporters/pdf/__init__.py backend/apps/core/exporters/pdf/base_pdf.py backend/apps/core/exporters/pdf/styles.py backend/apps/core/exporters/pdf/table_builder.py -> passed",
    "Phase 5 backend core Exporters smoke: ../.venv/bin/python import/build smoke for Excel/PDF exporter helpers -> passed",
    "Phase 5 backend core Exporters regression: ../.venv/bin/python -m pytest tests/test_api_core.py tests/test_api_license.py tests/test_api_boe.py apps/core/tests/test_mds_write_cutover.py -q -> 38 passed",
    "Phase 5 backend core materialized-view utilities Ruff: .venv/bin/ruff check backend/apps/core/materialized_views.py backend/apps/core/tasks.py backend/apps/core/tasks_materialized_views.py backend/apps/core/templatetags/core_tag.py backend/apps/core/tests/test_materialized_views.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core materialized-view utilities compile: .venv/bin/python -m py_compile backend/apps/core/materialized_views.py backend/apps/core/tasks.py backend/apps/core/tasks_materialized_views.py backend/apps/core/templatetags/core_tag.py backend/apps/core/tests/test_materialized_views.py -> passed",
    "Phase 5 backend core materialized-view utilities focused tests: ../.venv/bin/python -m pytest apps/core/tests/test_materialized_views.py -q -> 3 passed",
    "Phase 5 backend core materialized-view utilities regression: ../.venv/bin/python -m pytest apps/core/tests/test_materialized_views.py apps/core/tests/test_cache_signals.py apps/core/tests/test_mds_write_cutover.py tests/test_api_core.py -q -> 24 passed",
    "Phase 5 backend core templates Django check: ../.venv/bin/python manage.py check -> no issues",
    "Phase 5 backend core templates regression: ../.venv/bin/python -m pytest tests/test_url_routing.py tests/test_api_core.py -q -> 23 passed",
    "Phase 5 backend core templates duplicate script check: rg js/django_select2.js backend/apps/core/templates/core/list.html -> one include remains",
    "Phase 5 backend core management commands batch 1 Ruff: .venv/bin/ruff check audit_database_integrity.py audit_masters.py auto_import_masters.py cache_stats.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core management commands batch 1 compile: .venv/bin/python -m py_compile audit_database_integrity.py audit_masters.py auto_import_masters.py cache_stats.py -> passed",
    "Phase 5 backend core management commands batch 1 help checks: manage.py audit_database_integrity/audit_masters/auto_import_masters/cache_stats --help -> passed",
    "Phase 5 backend core management commands batch 1 regression: ../.venv/bin/python -m pytest apps/core/tests/test_materialized_views.py tests/test_api_core.py -q -> 12 passed",
    "Phase 5 backend core management commands batch 2 Ruff: .venv/bin/ruff check check_db_structure.py check_master_quality.py clean_duplicate_rowdetails.py clean_item_names.py clearcache.py convert_docx_to_pdf.py convert_license_table.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core management commands batch 2 compile: .venv/bin/python -m py_compile check_db_structure.py check_master_quality.py clean_duplicate_rowdetails.py clean_item_names.py clearcache.py convert_docx_to_pdf.py convert_license_table.py -> passed",
    "Phase 5 backend core management commands batch 2 help checks: manage.py check_db_structure/convert_docx_to_pdf/check_master_quality/clean_item_names/clearcache/clean_duplicate_rowdetails --help -> passed",
    "Phase 5 backend core management commands batch 2 regression: ../.venv/bin/python -m pytest apps/core/tests/test_check_master_quality.py -q -> 4 passed, 1 skipped",
    "Phase 5 backend core management commands batch 3 Ruff: .venv/bin/ruff check diff_masters.py export_masters_mds.py fetch_detail_conf.py fetch_exchange_rates.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core management commands batch 3 compile: .venv/bin/python -m py_compile diff_masters.py export_masters_mds.py fetch_detail_conf.py fetch_exchange_rates.py -> passed",
    "Phase 5 backend core management commands batch 3 help checks: manage.py diff_masters/export_masters_mds/fetch_detail_conf/fetch_exchange_rates --help -> passed",
    "Phase 5 backend core management commands batch 3 regression: ../.venv/bin/python -m pytest tests/test_export_masters_mds.py apps/core/tests/test_mds_write_cutover.py -q -> 20 passed",
    "Phase 5 backend core management commands batch 4 Ruff: .venv/bin/ruff check merge_masters.py rebuild_migrations.py reconcile_masters.py refresh_materialized_views.py reset_migration_history.py rqworker.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core management commands batch 4 compile: .venv/bin/python -m py_compile merge_masters.py rebuild_migrations.py reconcile_masters.py refresh_materialized_views.py reset_migration_history.py rqworker.py -> passed",
    "Phase 5 backend core management commands batch 4 help checks: manage.py merge_masters/rebuild_migrations/reconcile_masters/refresh_materialized_views/reset_migration_history/rqworker --help -> passed",
    "Phase 5 backend core management commands batch 4 regression: ../.venv/bin/python -m pytest apps/core/tests/test_reconcile_masters.py apps/core/tests/test_materialized_views.py -q -> 19 passed",
    "Phase 5 backend core management commands batch 5 Ruff: .venv/bin/ruff check seed_e132_plan_items.py sync_database_schema.py update_aluminium_foil_items.py update_dgft_descriptions.py update_sugar_items.py validate_db_fields.py _item_linking.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core management commands batch 5 compile: .venv/bin/python -m py_compile seed_e132_plan_items.py sync_database_schema.py update_aluminium_foil_items.py update_dgft_descriptions.py update_sugar_items.py validate_db_fields.py _item_linking.py -> passed",
    "Phase 5 backend core management commands batch 5 help checks: manage.py seed_e132_plan_items/sync_database_schema/update_aluminium_foil_items/update_dgft_descriptions/update_sugar_items/validate_db_fields --help -> passed",
    "Phase 5 backend core management commands batch 5 regression: ../.venv/bin/python -m pytest apps/license/tests/test_e132_plan.py tests/test_api_core.py apps/core/tests/test_mds_write_cutover.py -q -> 78 passed",
    "Phase 5 backend core scripts obsolete-reference scan: rg aro_letters/core.scripts.script/scripts.script/core.scripts.sion/request_sion_heads/render_to_pdf in backend docs tests -> no live references outside generated audit state",
    "Phase 5 backend core remaining scripts compile: python3 -m py_compile backend/apps/core/scripts/__init__.py calculate_balance.py calculation.py company_names.py ledger.py license_script.py -> passed",
    "Phase 5 backend core scripts regression: ../.venv/bin/python -m pytest tests/test_api_core.py apps/core/tests/test_mds_write_cutover.py -q -> 20 passed",
    "Phase 5 backend core migrations Ruff: .venv/bin/ruff check backend/apps/core/migrations --select F401,F821,F811,E741,F841,B904,B007 -> clean",
    "Phase 5 backend core migrations compile: .venv/bin/python -m py_compile backend/apps/core/migrations/*.py -> passed",
    "Phase 5 backend core migrations check: ../.venv/bin/python manage.py makemigrations core --check --dry-run -> no changes detected; DB connection warning only",
    "Phase 5 backend core migrations regression: ../.venv/bin/python -m pytest apps/core/tests/test_keyless_uid.py apps/license/tests/test_e132_plan.py -q -> 63 passed",
    "Phase 5 backend core tests Ruff: .venv/bin/ruff check backend/apps/core/tests/__init__.py test_check_master_quality.py test_keyless_uid.py test_reconcile_masters.py test_validation.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend core tests compile: .venv/bin/python -m py_compile backend/apps/core/tests/__init__.py test_check_master_quality.py test_keyless_uid.py test_reconcile_masters.py test_validation.py -> passed",
    "Phase 5 backend core tests regression: ../.venv/bin/python -m pytest apps/core/tests/test_check_master_quality.py apps/core/tests/test_keyless_uid.py apps/core/tests/test_reconcile_masters.py apps/core/tests/test_validation.py -q -> 109 passed, 1 skipped",
    "Phase 5 frontend master display focused tests: npm test -- --run src/pages/masters/masterDisplayFormatters.test.ts src/pages/masters/masterListConfig.test.ts -> 8 passed",
    "Phase 5 frontend master display lint: npm run lint -- src/pages/masters/masterDisplayFormatters.ts src/pages/masters/masterDisplayFormatters.test.ts src/pages/masters/BoeMergeModal.tsx src/pages/masters/LinkTradeModal.tsx src/pages/masters/tables/AllotmentsTable.tsx src/pages/masters/tables/IncentiveLicensesTable.tsx src/pages/masters/NestedFieldArray.tsx -> passed",
    "Phase 5 frontend master display typecheck: npm run typecheck -> passed",
    "Phase 5 frontend master display dependency audit: npm audit --audit-level=high -> 0 vulnerabilities",
    "Phase 5 backend golden-master scripts Ruff: .venv/bin/ruff check backend/scripts/golden_master_balance_exporters.py backend/scripts/golden_master_ledger_pdf.py backend/tests/test_export_masters_mds.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 5 backend golden-master scripts compile: .venv/bin/python -m py_compile backend/scripts/golden_master_balance_exporters.py backend/scripts/golden_master_ledger_pdf.py backend/tests/test_export_masters_mds.py -> passed",
    "Phase 5 backend golden-master ledger usage path: .venv/bin/python backend/scripts/golden_master_ledger_pdf.py -> usage printed without DB access, exit 2",
    "Phase 5 backend MDS export focused regression: .venv/bin/python -m pytest backend/tests/test_export_masters_mds.py -q -> 9 passed",
    "Phase 5 master-data shell scripts syntax: bash -n scripts/maintenance/_master_sync_lib.sh scripts/maintenance/apply-master-merge.sh scripts/maintenance/audit-and-diff-masters.sh scripts/maintenance/audit-and-merge-masters.sh scripts/maintenance/sync-masters.sh scripts/mds/_lib.sh scripts/mds/export-master-data.sh scripts/mds/load-master-data.sh scripts/mds/migrate-all-servers.sh scripts/mds/onboard-server.sh -> passed",
    "Phase 5 MDS shell help paths: scripts/mds/export-master-data.sh --help and scripts/mds/onboard-server.sh --help -> clean header-only usage output",
    "Phase 5 documentation stale path scan: rg old backend/core/frontend common/.jsx references in MDS/modularization docs -> only intentional stale-history note remains",
    "Phase 6 invoice model Ruff: .venv/bin/ruff check backend/apps/license/models/invoice.py backend/apps/license/tests/test_invoice_models.py backend/apps/license/migrations/0011_harden_invoice_validation.py backend/apps/license/migrations/0012_enforce_invoice_non_negative_constraints.py -> clean",
    "Phase 6 invoice model compile: .venv/bin/python -m py_compile backend/apps/license/models/invoice.py backend/apps/license/tests/test_invoice_models.py backend/apps/license/migrations/0011_harden_invoice_validation.py backend/apps/license/migrations/0012_enforce_invoice_non_negative_constraints.py -> passed",
    "Phase 6 invoice model regression: .venv/bin/python -m pytest backend/apps/license/tests/test_invoice_models.py -q -> 19 passed",
    "Phase 6 invoice model migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 invoice model Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 invoice model security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license balance Excel Ruff: .venv/bin/ruff check backend/apps/license/services/exporters/license_balance_excel.py backend/tests/test_api_license.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license balance Excel compile: .venv/bin/python -m py_compile backend/apps/license/services/exporters/license_balance_excel.py backend/tests/test_api_license.py -> passed",
    "Phase 6 license balance Excel regression: .venv/bin/python -m pytest backend/tests/test_api_license.py -q -> 13 passed",
    "Phase 6 license balance Excel Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license balance Excel migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license balance Excel security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 License tables Ruff: .venv/bin/ruff check backend/apps/license/tables.py backend/apps/license/tests/test_tables.py -> clean",
    "Phase 6 License tables selected Ruff: .venv/bin/ruff check backend/apps/license/tables.py backend/apps/license/tests/test_tables.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 License tables compile: .venv/bin/python -m py_compile backend/apps/license/tables.py backend/apps/license/tests/test_tables.py -> passed",
    "Phase 6 License tables regression: .venv/bin/python -m pytest backend/apps/license/tests/test_tables.py -q -> blocked/skipped; django_tables2 is not installed in .venv and is absent from backend/requirements*.txt, so pytest collected 0 runnable tests and returned exit code 5",
    "Phase 6 License tables Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 License tables migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 License tables dependency check: importlib.util.find_spec('django_tables2') -> None; rg backend/requirements*.txt -> no declaration",
    "Phase 6 License tables security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 balance calculator tests regression: .venv/bin/python -m pytest backend/apps/license/tests/test_balance_calculator.py -q -> 27 passed",
    "Phase 6 balance calculator tests Ruff: .venv/bin/ruff check backend/apps/license/tests/test_balance_calculator.py -> clean",
    "Phase 6 balance calculator tests selected Ruff: .venv/bin/ruff check backend/apps/license/tests/test_balance_calculator.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 balance calculator tests compile: .venv/bin/python -m py_compile backend/apps/license/tests/test_balance_calculator.py -> passed",
    "Phase 6 balance calculator tests Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 balance calculator tests migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 balance calculator tests security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 E132 planning tests regression: .venv/bin/python -m pytest backend/apps/license/tests/test_e132_plan.py -q -> 59 passed",
    "Phase 6 E132 planning tests Ruff: .venv/bin/ruff check backend/apps/license/tests/test_e132_plan.py -> clean",
    "Phase 6 E132 planning tests selected Ruff: .venv/bin/ruff check backend/apps/license/tests/test_e132_plan.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 E132 planning tests compile: .venv/bin/python -m py_compile backend/apps/license/tests/test_e132_plan.py -> passed",
    "Phase 6 E132 planning tests Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 E132 planning tests migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 E132 planning tests security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 E5 planning tests regression: .venv/bin/python -m pytest backend/apps/license/tests/test_e5_plan.py -q -> 43 passed",
    "Phase 6 E5 planning tests Ruff: .venv/bin/ruff check backend/apps/license/tests/test_e5_plan.py -> clean",
    "Phase 6 E5 planning tests compile: .venv/bin/python -m py_compile backend/apps/license/tests/test_e5_plan.py -> passed",
    "Phase 6 E5 planning tests Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 E5 planning tests migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 E5 planning tests security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 E1 planning tests regression: .venv/bin/python -m pytest backend/apps/license/tests/test_e1_plan.py -q -> 34 passed",
    "Phase 6 E1 planning tests Ruff: .venv/bin/ruff check backend/apps/license/tests/test_e1_plan.py -> clean",
    "Phase 6 E1 planning tests compile: .venv/bin/python -m py_compile backend/apps/license/tests/test_e1_plan.py -> passed",
    "Phase 6 E1 planning tests Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 E1 planning tests migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 E1 planning tests security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 License query builder regression: .venv/bin/python -m pytest backend/apps/license/tests/test_query_builder.py -q -> 13 passed",
    "Phase 6 License query builder Ruff: .venv/bin/ruff check backend/apps/license/utils/query_builder.py backend/apps/license/tests/test_query_builder.py -> clean",
    "Phase 6 License query builder selected Ruff: .venv/bin/ruff check backend/apps/license/utils/query_builder.py backend/apps/license/tests/test_query_builder.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 License query builder compile: .venv/bin/python -m py_compile backend/apps/license/utils/query_builder.py backend/apps/license/tests/test_query_builder.py -> passed",
    "Phase 6 License query builder Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 License query builder migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 License query builder diff check: git diff --check -- backend/apps/license/utils/query_builder.py backend/apps/license/tests/test_query_builder.py -> clean",
    "Phase 6 License query builder security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 License helper dead-code reference scan: rg item_wise_debiting/item_wise_allotment/fetch_item_details/apps.license.helper/license.helper -> no references outside the deleted file",
    "Phase 6 License helper regression: .venv/bin/python -m pytest backend/tests/test_api_license.py backend/apps/license/tests/test_query_builder.py -q -> 26 passed",
    "Phase 6 License helper compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 License helper Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 License helper migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 License helper diff check: git diff --check -- backend/apps/license/helper.py -> clean",
    "Phase 6 License helper broad Ruff: .venv/bin/ruff check backend/apps/license --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> blocked by 224 pre-existing findings in other pending License files, none from deleted helper.py",
    "Phase 6 License helper security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 License management package marker Ruff: .venv/bin/ruff check backend/apps/license/management/__init__.py -> clean",
    "Phase 6 License management package marker compile: .venv/bin/python -m py_compile backend/apps/license/management/__init__.py -> passed",
    "Phase 6 License management package marker Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 License management package marker migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 License management package marker diff check: git diff --check -- backend/apps/license/management/__init__.py -> clean",
    "Phase 6 License management package marker security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 License management commands package marker Ruff: .venv/bin/ruff check backend/apps/license/management/commands/__init__.py -> clean",
    "Phase 6 License management commands package marker compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/__init__.py -> passed",
    "Phase 6 License management commands package marker Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 License management commands package marker migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 License management commands package marker diff check: git diff --check -- backend/apps/license/management/commands/__init__.py -> clean",
    "Phase 6 License management commands package marker security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 delete_licenses_by_exporter regression: .venv/bin/python -m pytest backend/apps/license/tests/test_delete_licenses_by_exporter_command.py -q -> 4 passed",
    "Phase 6 delete_licenses_by_exporter selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/delete_licenses_by_exporter.py backend/apps/license/tests/test_delete_licenses_by_exporter_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 delete_licenses_by_exporter Ruff: .venv/bin/ruff check backend/apps/license/management/commands/delete_licenses_by_exporter.py backend/apps/license/tests/test_delete_licenses_by_exporter_command.py -> clean",
    "Phase 6 delete_licenses_by_exporter compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/delete_licenses_by_exporter.py backend/apps/license/tests/test_delete_licenses_by_exporter_command.py -> passed",
    "Phase 6 delete_licenses_by_exporter help: .venv/bin/python backend/manage.py delete_licenses_by_exporter --help -> passed",
    "Phase 6 delete_licenses_by_exporter Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 delete_licenses_by_exporter migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 delete_licenses_by_exporter diff check: git diff --check -- backend/apps/license/management/commands/delete_licenses_by_exporter.py backend/apps/license/tests/test_delete_licenses_by_exporter_command.py -> clean",
    "Phase 6 delete_licenses_by_exporter security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 migrate_purchase_status_np_to_mi regression: .venv/bin/python -m pytest backend/apps/license/tests/test_migrate_purchase_status_command.py -q -> 4 passed",
    "Phase 6 migrate_purchase_status_np_to_mi selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/migrate_purchase_status_np_to_mi.py backend/apps/license/tests/test_migrate_purchase_status_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 migrate_purchase_status_np_to_mi Ruff: .venv/bin/ruff check backend/apps/license/management/commands/migrate_purchase_status_np_to_mi.py backend/apps/license/tests/test_migrate_purchase_status_command.py -> clean",
    "Phase 6 migrate_purchase_status_np_to_mi compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/migrate_purchase_status_np_to_mi.py backend/apps/license/tests/test_migrate_purchase_status_command.py -> passed",
    "Phase 6 migrate_purchase_status_np_to_mi help: .venv/bin/python backend/manage.py migrate_purchase_status_np_to_mi --help -> passed",
    "Phase 6 migrate_purchase_status_np_to_mi Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 migrate_purchase_status_np_to_mi migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 migrate_purchase_status_np_to_mi diff check: git diff --check -- backend/apps/license/management/commands/migrate_purchase_status_np_to_mi.py backend/apps/license/tests/test_migrate_purchase_status_command.py -> clean",
    "Phase 6 migrate_purchase_status_np_to_mi security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 populate_license_items regression: .venv/bin/python -m pytest backend/apps/license/tests/test_populate_license_items_command.py -q -> 7 passed",
    "Phase 6 populate_license_items selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/populate_license_items.py backend/apps/license/tests/test_populate_license_items_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 populate_license_items Ruff: .venv/bin/ruff check backend/apps/license/management/commands/populate_license_items.py backend/apps/license/tests/test_populate_license_items_command.py -> clean",
    "Phase 6 populate_license_items compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/populate_license_items.py backend/apps/license/tests/test_populate_license_items_command.py -> passed",
    "Phase 6 populate_license_items compileall: .venv/bin/python -m compileall -q backend/apps/license/management/commands/populate_license_items.py backend/apps/license/tests/test_populate_license_items_command.py -> passed",
    "Phase 6 populate_license_items help: .venv/bin/python backend/manage.py populate_license_items --help -> passed",
    "Phase 6 populate_license_items import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported Command -> passed",
    "Phase 6 populate_license_items Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 populate_license_items migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 populate_license_items diff check: git diff --check -- backend/apps/license/management/commands/populate_license_items.py backend/apps/license/tests/test_populate_license_items_command.py -> clean",
    "Phase 6 populate_license_items security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 repair_license_subtables regression: .venv/bin/python -m pytest backend/apps/license/tests/test_repair_license_subtables_command.py -q -> 5 passed",
    "Phase 6 repair_license_subtables selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/repair_license_subtables.py backend/apps/license/tests/test_repair_license_subtables_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 repair_license_subtables Ruff: .venv/bin/ruff check backend/apps/license/management/commands/repair_license_subtables.py backend/apps/license/tests/test_repair_license_subtables_command.py -> clean",
    "Phase 6 repair_license_subtables compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/repair_license_subtables.py backend/apps/license/tests/test_repair_license_subtables_command.py -> passed",
    "Phase 6 repair_license_subtables compileall: .venv/bin/python -m compileall -q backend/apps/license/management/commands/repair_license_subtables.py backend/apps/license/tests/test_repair_license_subtables_command.py -> passed",
    "Phase 6 repair_license_subtables help: .venv/bin/python backend/manage.py repair_license_subtables --help -> passed",
    "Phase 6 repair_license_subtables import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported Command -> passed",
    "Phase 6 repair_license_subtables Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 repair_license_subtables migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 repair_license_subtables diff check: git diff --check -- backend/apps/license/management/commands/repair_license_subtables.py backend/apps/license/tests/test_repair_license_subtables_command.py -> clean",
    "Phase 6 repair_license_subtables security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 resync_local_to_server regression: .venv/bin/python -m pytest backend/apps/license/tests/test_resync_local_to_server_command.py -q -> 9 passed",
    "Phase 6 resync_local_to_server selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/resync_local_to_server.py backend/apps/license/tests/test_resync_local_to_server_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 resync_local_to_server Ruff: .venv/bin/ruff check backend/apps/license/management/commands/resync_local_to_server.py backend/apps/license/tests/test_resync_local_to_server_command.py -> clean",
    "Phase 6 resync_local_to_server compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/resync_local_to_server.py backend/apps/license/tests/test_resync_local_to_server_command.py -> passed",
    "Phase 6 resync_local_to_server compileall: .venv/bin/python -m compileall -q backend/apps/license/management/commands/resync_local_to_server.py backend/apps/license/tests/test_resync_local_to_server_command.py -> passed",
    "Phase 6 resync_local_to_server help: .venv/bin/python backend/manage.py resync_local_to_server --help -> passed",
    "Phase 6 resync_local_to_server import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported Command -> passed",
    "Phase 6 resync_local_to_server Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 resync_local_to_server migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 resync_local_to_server diff check: git diff --check -- backend/apps/license/management/commands/resync_local_to_server.py backend/apps/license/tests/test_resync_local_to_server_command.py -> clean",
    "Phase 6 resync_local_to_server security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 sync_licenses regression: .venv/bin/python -m pytest backend/apps/license/tests/test_sync_licenses_command.py -q -> 4 passed",
    "Phase 6 sync_licenses selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/sync_licenses.py backend/apps/license/tests/test_sync_licenses_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 sync_licenses Ruff: .venv/bin/ruff check backend/apps/license/management/commands/sync_licenses.py backend/apps/license/tests/test_sync_licenses_command.py -> clean",
    "Phase 6 sync_licenses compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/sync_licenses.py backend/apps/license/tests/test_sync_licenses_command.py -> passed",
    "Phase 6 sync_licenses compileall: .venv/bin/python -m compileall -q backend/apps/license/management/commands/sync_licenses.py backend/apps/license/tests/test_sync_licenses_command.py -> passed",
    "Phase 6 sync_licenses help: .venv/bin/python backend/manage.py sync_licenses --help -> passed",
    "Phase 6 sync_licenses import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported Command -> passed",
    "Phase 6 sync_licenses Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 sync_licenses migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 sync_licenses diff check: git diff --check -- backend/apps/license/management/commands/sync_licenses.py backend/apps/license/tests/test_sync_licenses_command.py -> clean",
    "Phase 6 sync_licenses security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 update_balance_cif regression: .venv/bin/python -m pytest backend/apps/license/tests/test_update_balance_cif_command.py -q -> 6 passed",
    "Phase 6 update_balance_cif selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/update_balance_cif.py backend/apps/license/tests/test_update_balance_cif_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 update_balance_cif Ruff: .venv/bin/ruff check backend/apps/license/management/commands/update_balance_cif.py backend/apps/license/tests/test_update_balance_cif_command.py -> clean",
    "Phase 6 update_balance_cif compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/update_balance_cif.py backend/apps/license/tests/test_update_balance_cif_command.py -> passed",
    "Phase 6 update_balance_cif compileall: .venv/bin/python -m compileall -q backend/apps/license/management/commands/update_balance_cif.py backend/apps/license/tests/test_update_balance_cif_command.py -> passed",
    "Phase 6 update_balance_cif help: .venv/bin/python backend/manage.py update_balance_cif --help -> passed",
    "Phase 6 update_balance_cif import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported Command -> passed",
    "Phase 6 update_balance_cif Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 update_balance_cif migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 update_balance_cif diff check: git diff --check -- backend/apps/license/management/commands/update_balance_cif.py backend/apps/license/tests/test_update_balance_cif_command.py -> clean",
    "Phase 6 update_balance_cif security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 update_license_expiry regression: .venv/bin/python -m pytest backend/apps/license/tests/test_update_license_expiry_command.py -q -> 13 passed",
    "Phase 6 update_license_expiry selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/update_license_expiry.py backend/apps/license/tests/test_update_license_expiry_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 update_license_expiry Ruff: .venv/bin/ruff check backend/apps/license/management/commands/update_license_expiry.py backend/apps/license/tests/test_update_license_expiry_command.py -> clean",
    "Phase 6 update_license_expiry compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/update_license_expiry.py backend/apps/license/tests/test_update_license_expiry_command.py -> passed",
    "Phase 6 update_license_expiry compileall: .venv/bin/python -m compileall -q backend/apps/license/management/commands/update_license_expiry.py backend/apps/license/tests/test_update_license_expiry_command.py -> passed",
    "Phase 6 update_license_expiry help: .venv/bin/python backend/manage.py update_license_expiry --help -> passed",
    "Phase 6 update_license_expiry import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported Command -> passed",
    "Phase 6 update_license_expiry Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 update_license_expiry migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 update_license_expiry diff check: git diff --check -- backend/apps/license/management/commands/update_license_expiry.py backend/apps/license/tests/test_update_license_expiry_command.py -> clean",
    "Phase 6 update_license_expiry security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 upload_dfia_copies regression: .venv/bin/python -m pytest backend/apps/license/tests/test_upload_dfia_copies_command.py -q -> 12 passed",
    "Phase 6 upload_dfia_copies selected Ruff: .venv/bin/ruff check backend/apps/license/management/commands/upload_dfia_copies.py backend/apps/license/tests/test_upload_dfia_copies_command.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 upload_dfia_copies Ruff: .venv/bin/ruff check backend/apps/license/management/commands/upload_dfia_copies.py backend/apps/license/tests/test_upload_dfia_copies_command.py -> clean",
    "Phase 6 upload_dfia_copies compile: .venv/bin/python -m py_compile backend/apps/license/management/commands/upload_dfia_copies.py backend/apps/license/tests/test_upload_dfia_copies_command.py -> passed",
    "Phase 6 upload_dfia_copies compileall: .venv/bin/python -m compileall -q backend/apps/license/management/commands/upload_dfia_copies.py backend/apps/license/tests/test_upload_dfia_copies_command.py -> passed",
    "Phase 6 upload_dfia_copies help: .venv/bin/python backend/manage.py upload_dfia_copies --help -> passed",
    "Phase 6 upload_dfia_copies import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported Command -> passed",
    "Phase 6 upload_dfia_copies Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 upload_dfia_copies migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 upload_dfia_copies diff check: git diff --check -- backend/apps/license/management/commands/upload_dfia_copies.py backend/apps/license/tests/test_upload_dfia_copies_command.py -> clean",
    "Phase 6 upload_dfia_copies security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0001 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0001_initial.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0001 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0001_initial.py -> clean",
    "Phase 6 license migration 0001 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0001_initial.py -> passed",
    "Phase 6 license migration 0001 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0001_initial.py -> passed",
    "Phase 6 license migration 0001 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, Migration.initial=True, 30 operations -> passed",
    "Phase 6 license migration 0001 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0001 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0001 showmigrations plan: .venv/bin/python backend/manage.py showmigrations license --plan -> blocked by sandboxed PostgreSQL connection Operation not permitted",
    "Phase 6 license migration 0001 diff check: git diff --check -- backend/apps/license/migrations/0001_initial.py -> clean",
    "Phase 6 license migration 0001 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0002 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0002_scheme_and_notification_to_fk.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0002 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0002_scheme_and_notification_to_fk.py -> clean",
    "Phase 6 license migration 0002 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0002_scheme_and_notification_to_fk.py -> passed",
    "Phase 6 license migration 0002 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0002_scheme_and_notification_to_fk.py -> passed",
    "Phase 6 license migration 0002 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, Migration.atomic=False, 9 operations -> passed",
    "Phase 6 license migration 0002 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0002 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0002 diff check: git diff --check -- backend/apps/license/migrations/0002_scheme_and_notification_to_fk.py -> clean",
    "Phase 6 license migration 0002 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0003 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0003_remove_licensedetailsmodel_license_lic_notific_5b1519_idx_and_more.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0003 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0003_remove_licensedetailsmodel_license_lic_notific_5b1519_idx_and_more.py -> clean",
    "Phase 6 license migration 0003 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0003_remove_licensedetailsmodel_license_lic_notific_5b1519_idx_and_more.py -> passed",
    "Phase 6 license migration 0003 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0003_remove_licensedetailsmodel_license_lic_notific_5b1519_idx_and_more.py -> passed",
    "Phase 6 license migration 0003 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, 2 operations -> passed",
    "Phase 6 license migration 0003 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0003 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0003 diff check: git diff --check -- backend/apps/license/migrations/0003_remove_licensedetailsmodel_license_lic_notific_5b1519_idx_and_more.py -> clean",
    "Phase 6 license migration 0003 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0004 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0004_licensedetailsmodel_archived_exporter_name_and_more.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0004 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0004_licensedetailsmodel_archived_exporter_name_and_more.py -> clean",
    "Phase 6 license migration 0004 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0004_licensedetailsmodel_archived_exporter_name_and_more.py -> passed",
    "Phase 6 license migration 0004 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0004_licensedetailsmodel_archived_exporter_name_and_more.py -> passed",
    "Phase 6 license migration 0004 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, 2 operations -> passed",
    "Phase 6 license migration 0004 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0004 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0004 diff check: git diff --check -- backend/apps/license/migrations/0004_licensedetailsmodel_archived_exporter_name_and_more.py -> clean",
    "Phase 6 license migration 0004 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0005 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0005_licensebalance_licenseflags_licensenotes_and_more.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0005 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0005_licensebalance_licenseflags_licensenotes_and_more.py -> clean",
    "Phase 6 license migration 0005 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0005_licensebalance_licenseflags_licensenotes_and_more.py -> passed",
    "Phase 6 license migration 0005 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0005_licensebalance_licenseflags_licensenotes_and_more.py -> passed",
    "Phase 6 license migration 0005 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, Migration.atomic=False, 30 operations -> passed",
    "Phase 6 license migration 0005 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0005 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0005 diff check: git diff --check -- backend/apps/license/migrations/0005_licensebalance_licenseflags_licensenotes_and_more.py -> clean",
    "Phase 6 license migration 0005 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0006 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0006_drop_obsolete_scheme_notification_columns.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0006 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0006_drop_obsolete_scheme_notification_columns.py -> clean",
    "Phase 6 license migration 0006 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0006_drop_obsolete_scheme_notification_columns.py -> passed",
    "Phase 6 license migration 0006 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0006_drop_obsolete_scheme_notification_columns.py -> passed",
    "Phase 6 license migration 0006 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, 1 operation -> passed",
    "Phase 6 license migration 0006 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0006 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0006 diff check: git diff --check -- backend/apps/license/migrations/0006_drop_obsolete_scheme_notification_columns.py -> clean",
    "Phase 6 license migration 0006 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0007 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0007_drop_obsolete_subtable_columns.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0007 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0007_drop_obsolete_subtable_columns.py -> clean",
    "Phase 6 license migration 0007 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0007_drop_obsolete_subtable_columns.py -> passed",
    "Phase 6 license migration 0007 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0007_drop_obsolete_subtable_columns.py -> passed",
    "Phase 6 license migration 0007 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, 1 operation, 18 orphan columns -> passed",
    "Phase 6 license migration 0007 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0007 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0007 diff check: git diff --check -- backend/apps/license/migrations/0007_drop_obsolete_subtable_columns.py -> clean",
    "Phase 6 license migration 0007 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0009 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0009_licenseitemplan.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0009 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0009_licenseitemplan.py -> clean",
    "Phase 6 license migration 0009 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0009_licenseitemplan.py -> passed",
    "Phase 6 license migration 0009 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0009_licenseitemplan.py -> passed",
    "Phase 6 license migration 0009 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, 1 operation -> passed",
    "Phase 6 license migration 0009 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0009 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0009 diff check: git diff --check -- backend/apps/license/migrations/0009_licenseitemplan.py -> clean",
    "Phase 6 license migration 0009 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migration 0010 selected Ruff: .venv/bin/ruff check backend/apps/license/migrations/0010_licenseitemplan_item_name_licenseitemplan_unit_price_and_more.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license migration 0010 Ruff: .venv/bin/ruff check backend/apps/license/migrations/0010_licenseitemplan_item_name_licenseitemplan_unit_price_and_more.py -> clean",
    "Phase 6 license migration 0010 compile: .venv/bin/python -m py_compile backend/apps/license/migrations/0010_licenseitemplan_item_name_licenseitemplan_unit_price_and_more.py -> passed",
    "Phase 6 license migration 0010 compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/0010_licenseitemplan_item_name_licenseitemplan_unit_price_and_more.py -> passed",
    "Phase 6 license migration 0010 import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported migration, 4 operations -> passed",
    "Phase 6 license migration 0010 Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migration 0010 migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migration 0010 diff check: git diff --check -- backend/apps/license/migrations/0010_licenseitemplan_item_name_licenseitemplan_unit_price_and_more.py -> clean",
    "Phase 6 license migration 0010 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license migrations package marker Ruff: .venv/bin/ruff check backend/apps/license/migrations/__init__.py -> clean",
    "Phase 6 license migrations package marker compile: .venv/bin/python -m py_compile backend/apps/license/migrations/__init__.py -> passed",
    "Phase 6 license migrations package marker compileall: .venv/bin/python -m compileall -q backend/apps/license/migrations/__init__.py -> passed",
    "Phase 6 license migrations package marker import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported apps.license.migrations -> passed",
    "Phase 6 license migrations package marker Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license migrations package marker migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license migrations package marker diff check: git diff --check -- backend/apps/license/migrations/__init__.py -> clean",
    "Phase 6 license migrations package marker security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 models_integration dead-code reference scan: rg models_integration/LicenseBalanceMixin/LicenseItemBalanceMixin backend docs tests excluding generated audit JSON -> no references",
    "Phase 6 models_integration compileall after deletion: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 models_integration regression after deletion: .venv/bin/python -m pytest backend/apps/license/tests/test_balance_calculator.py backend/apps/license/tests/test_query_builder.py -q -> 40 passed",
    "Phase 6 models_integration broad License Ruff: .venv/bin/ruff check backend/apps/license --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> blocked by 209 pre-existing findings in other pending License files, none related to deleted models_integration.py",
    "Phase 6 models_integration Django check after deletion: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 models_integration migration check after deletion: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 models_integration diff check: git diff --check -- backend/apps/license/models_integration.py -> clean",
    "Phase 6 models_integration security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 parsers package marker Ruff: .venv/bin/ruff check backend/apps/license/parsers/__init__.py -> clean",
    "Phase 6 parsers package marker compile: .venv/bin/python -m py_compile backend/apps/license/parsers/__init__.py -> passed",
    "Phase 6 parsers package marker compileall: .venv/bin/python -m compileall -q backend/apps/license/parsers/__init__.py -> passed",
    "Phase 6 parsers package marker import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported apps.license.parsers -> passed",
    "Phase 6 parsers package marker Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 parsers package marker migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 parsers package marker diff check: git diff --check -- backend/apps/license/parsers/__init__.py -> clean",
    "Phase 6 parsers package marker security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license write serializer regression: .venv/bin/python -m pytest backend/tests/test_api_license.py backend/apps/license/tests/test_query_builder.py -q -> 26 passed",
    "Phase 6 license write serializer Ruff: .venv/bin/ruff check backend/apps/license/serializers/_license_write.py -> clean",
    "Phase 6 license write serializer compile: .venv/bin/python -m py_compile backend/apps/license/serializers/_license_write.py -> passed",
    "Phase 6 license write serializer compileall: .venv/bin/python -m compileall -q backend/apps/license/serializers/_license_write.py -> passed",
    "Phase 6 license write serializer import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported LicenseWriteMixin -> passed",
    "Phase 6 license write serializer Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license write serializer migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license write serializer diff check: git diff --check -- backend/apps/license/serializers/_license_write.py -> clean",
    "Phase 6 license write serializer security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 incentive serializers regression: .venv/bin/python -m pytest backend/apps/license/tests/test_incentive_serializers.py -q -> 3 passed",
    "Phase 6 incentive serializers Ruff: .venv/bin/ruff check backend/apps/license/serializers/incentive.py backend/apps/license/tests/test_incentive_serializers.py -> clean",
    "Phase 6 incentive serializers compile: .venv/bin/python -m py_compile backend/apps/license/serializers/incentive.py backend/apps/license/tests/test_incentive_serializers.py -> passed",
    "Phase 6 incentive serializers compileall: .venv/bin/python -m compileall -q backend/apps/license/serializers/incentive.py backend/apps/license/tests/test_incentive_serializers.py -> passed",
    "Phase 6 incentive serializers import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported IncentiveLicenseSerializer and LicenseItemPlanSerializer; expiry field read_only=False -> passed",
    "Phase 6 incentive serializers Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 incentive serializers migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 incentive serializers diff check: git diff --check -- backend/apps/license/serializers/incentive.py backend/apps/license/tests/test_incentive_serializers.py -> clean",
    "Phase 6 incentive serializers security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 balance calculator regression: .venv/bin/python -m pytest backend/apps/license/tests/test_balance_calculator.py -q -> 30 passed",
    "Phase 6 balance calculator all-conditions slice: .venv/bin/python -m pytest backend/tests/test_all_conditions.py::TestLicenseBalanceCalculator backend/tests/test_all_conditions.py::TestItemBalanceCalculator -q -> 26 passed",
    "Phase 6 balance calculator Ruff: .venv/bin/ruff check backend/apps/license/services/balance_calculator.py backend/apps/license/tests/test_balance_calculator.py -> clean",
    "Phase 6 balance calculator compile: .venv/bin/python -m py_compile backend/apps/license/services/balance_calculator.py backend/apps/license/tests/test_balance_calculator.py -> passed",
    "Phase 6 balance calculator compileall: .venv/bin/python -m compileall -q backend/apps/license/services/balance_calculator.py backend/apps/license/tests/test_balance_calculator.py -> passed",
    "Phase 6 balance calculator import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported calculators and quantize_2dp('1.235') -> 1.24",
    "Phase 6 balance calculator Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 balance calculator migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 balance calculator diff check: git diff --check -- backend/apps/license/services/balance_calculator.py backend/apps/license/tests/test_balance_calculator.py -> clean",
    "Phase 6 balance calculator security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 DGFT ownership helper regression: .venv/bin/python -m pytest backend/apps/license/tests/test_dgft_ownership.py -q -> 5 passed",
    "Phase 6 DGFT ownership helper Ruff: .venv/bin/ruff check backend/apps/license/services/dgft_ownership.py backend/apps/license/tests/test_dgft_ownership.py -> clean",
    "Phase 6 DGFT ownership helper compile: .venv/bin/python -m py_compile backend/apps/license/services/dgft_ownership.py backend/apps/license/tests/test_dgft_ownership.py -> passed",
    "Phase 6 DGFT ownership helper compileall: .venv/bin/python -m compileall -q backend/apps/license/services/dgft_ownership.py backend/apps/license/tests/test_dgft_ownership.py -> passed",
    "Phase 6 DGFT ownership helper import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported fetch_scrip_ownership and DGFT_URL -> passed",
    "Phase 6 DGFT ownership command help: .venv/bin/python backend/manage.py update_license_ownership --help -> passed",
    "Phase 6 DGFT ownership helper Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 DGFT ownership helper migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 DGFT ownership helper diff check: git diff --check -- backend/apps/license/services/dgft_ownership.py backend/apps/license/tests/test_dgft_ownership.py -> clean",
    "Phase 6 DGFT ownership helper security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 E132 planning engine regression: .venv/bin/python -m pytest backend/apps/license/tests/test_e132_plan.py -q -> 59 passed",
    "Phase 6 E132 planning engine Ruff: .venv/bin/ruff check backend/apps/license/services/e132_plan.py backend/apps/license/tests/test_e132_plan.py -> clean",
    "Phase 6 E132 planning engine compile: .venv/bin/python -m py_compile backend/apps/license/services/e132_plan.py backend/apps/license/tests/test_e132_plan.py -> passed",
    "Phase 6 E132 planning engine compileall: .venv/bin/python -m compileall -q backend/apps/license/services/e132_plan.py backend/apps/license/tests/test_e132_plan.py -> passed",
    "Phase 6 E132 planning engine import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported plan_e132 and classify_e132_record('2106','yeast') -> Yeast - E132",
    "Phase 6 E132 planning engine Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 E132 planning engine migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 E132 planning engine diff check: git diff --check -- backend/apps/license/services/e132_plan.py backend/apps/license/tests/test_e132_plan.py -> clean",
    "Phase 6 E132 planning engine security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 ledger service focused regression: .venv/bin/python -m pytest backend/apps/license/tests/test_ledger_service.py -q -> 5 passed",
    "Phase 6 ledger service API regression: .venv/bin/python -m pytest backend/apps/license/tests/test_ledger_service.py backend/tests/test_api_trade.py::TestLicenseLedgerAPI -q -> 7 passed",
    "Phase 6 ledger service Ruff: .venv/bin/ruff check backend/apps/license/services/ledger_service.py backend/apps/license/tests/test_ledger_service.py -> clean",
    "Phase 6 ledger service selected Ruff: .venv/bin/ruff check backend/apps/license/services/ledger_service.py backend/apps/license/tests/test_ledger_service.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 ledger service compile: .venv/bin/python -m py_compile backend/apps/license/services/ledger_service.py backend/apps/license/tests/test_ledger_service.py -> passed",
    "Phase 6 ledger service compileall: .venv/bin/python -m compileall -q backend/apps/license/services/ledger_service.py backend/apps/license/tests/test_ledger_service.py -> passed",
    "Phase 6 ledger service import verification: .venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings imported prepare_incentive_data, build_license_queryset, and get_ledger_summary -> passed",
    "Phase 6 ledger service Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 ledger service migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 ledger service diff check: git diff --check -- backend/apps/license/services/ledger_service.py backend/apps/license/tests/test_ledger_service.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 ledger service security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 plan enforcement regression: .venv/bin/python -m pytest backend/apps/license/tests/test_plan_enforcement.py -q -> 2 passed",
    "Phase 6 plan enforcement Ruff: .venv/bin/ruff check backend/apps/license/services/plan_enforcement.py backend/apps/license/tests/test_plan_enforcement.py -> clean",
    "Phase 6 plan enforcement selected Ruff: .venv/bin/ruff check backend/apps/license/services/plan_enforcement.py backend/apps/license/tests/test_plan_enforcement.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 plan enforcement compile: .venv/bin/python -m py_compile backend/apps/license/services/plan_enforcement.py backend/apps/license/tests/test_plan_enforcement.py -> passed",
    "Phase 6 plan enforcement compileall: .venv/bin/python -m compileall -q backend/apps/license/services/plan_enforcement.py backend/apps/license/tests/test_plan_enforcement.py -> passed",
    "Phase 6 plan enforcement import verification: .venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings imported helpers; live_allotted_qty(None) -> 0.000 and live_allotted_value_for(None) -> 0.00",
    "Phase 6 plan enforcement Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 plan enforcement migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 plan enforcement diff check: git diff --check -- backend/apps/license/services/plan_enforcement.py backend/apps/license/tests/test_plan_enforcement.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 plan enforcement security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 plan grouping regression: .venv/bin/python -m pytest backend/apps/license/tests/test_plan_grouping.py -q -> 3 passed",
    "Phase 6 plan grouping Ruff: .venv/bin/ruff check backend/apps/license/services/plan_grouping.py backend/apps/license/tests/test_plan_grouping.py -> clean",
    "Phase 6 plan grouping selected Ruff: .venv/bin/ruff check backend/apps/license/services/plan_grouping.py backend/apps/license/tests/test_plan_grouping.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 plan grouping compile: .venv/bin/python -m py_compile backend/apps/license/services/plan_grouping.py backend/apps/license/tests/test_plan_grouping.py -> passed",
    "Phase 6 plan grouping compileall: .venv/bin/python -m compileall -q backend/apps/license/services/plan_grouping.py backend/apps/license/tests/test_plan_grouping.py -> passed",
    "Phase 6 plan grouping import verification: .venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings imported helpers; plan_group_key(None) -> ID:None and group_ids_of(unsaved) -> []",
    "Phase 6 plan grouping Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 plan grouping migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 plan grouping diff check: git diff --check -- backend/apps/license/services/plan_grouping.py backend/apps/license/tests/test_plan_grouping.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 plan grouping security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 validation service regression: .venv/bin/python -m pytest backend/apps/license/tests/test_validation_service.py -q -> 4 passed",
    "Phase 6 validation service Ruff: .venv/bin/ruff check backend/apps/license/services/validation_service.py backend/apps/license/tests/test_validation_service.py -> clean",
    "Phase 6 validation service selected Ruff: .venv/bin/ruff check backend/apps/license/services/validation_service.py backend/apps/license/tests/test_validation_service.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 validation service compile: .venv/bin/python -m py_compile backend/apps/license/services/validation_service.py backend/apps/license/tests/test_validation_service.py -> passed",
    "Phase 6 validation service compileall: .venv/bin/python -m compileall -q backend/apps/license/services/validation_service.py backend/apps/license/tests/test_validation_service.py -> passed",
    "Phase 6 validation service import verification: .venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings imported LicenseValidationService; validate_license_active(None) -> License is required",
    "Phase 6 validation service Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 validation service migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 validation service diff check: git diff --check -- backend/apps/license/services/validation_service.py backend/apps/license/tests/test_validation_service.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 validation service security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license signals regression: .venv/bin/python -m pytest backend/apps/license/tests/test_signals.py -q -> 15 passed",
    "Phase 6 license signals Ruff: .venv/bin/ruff check backend/apps/license/signals.py backend/apps/license/tests/test_signals.py -> clean",
    "Phase 6 license signals selected Ruff: .venv/bin/ruff check backend/apps/license/signals.py backend/apps/license/tests/test_signals.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 license signals compile: .venv/bin/python -m py_compile backend/apps/license/signals.py backend/apps/license/tests/test_signals.py -> passed",
    "Phase 6 license signals compileall: .venv/bin/python -m compileall -q backend/apps/license/signals.py backend/apps/license/tests/test_signals.py -> passed",
    "Phase 6 license signals import verification: .venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings imported suspend_license_flag_recalc, update_license_flags, and update_license_on_import_item_change -> passed",
    "Phase 6 license signals Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license signals migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license signals diff check: git diff --check -- backend/apps/license/signals.py backend/apps/license/tests/test_signals.py -> clean",
    "Phase 6 license signals security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 table columns focused regression: .venv/bin/python -m pytest backend/apps/license/tests/test_table_columns.py -q -> skipped/blocked because django_tables2 is not installed in the local venv",
    "Phase 6 table columns Ruff: .venv/bin/ruff check backend/apps/license/table_columns.py backend/apps/license/tests/test_table_columns.py -> clean",
    "Phase 6 table columns selected Ruff: .venv/bin/ruff check backend/apps/license/table_columns.py backend/apps/license/tests/test_table_columns.py --select F401,F821,F811,E741,F841,UP035,UP006,UP045,B904,B007 -> clean",
    "Phase 6 table columns compile: .venv/bin/python -m py_compile backend/apps/license/table_columns.py backend/apps/license/tests/test_table_columns.py -> passed",
    "Phase 6 table columns compileall: .venv/bin/python -m compileall -q backend/apps/license/table_columns.py backend/apps/license/tests/test_table_columns.py -> passed",
    "Phase 6 table columns import verification: .venv/bin/python -c 'import django_tables2' -> blocked, ModuleNotFoundError: No module named django_tables2",
    "Phase 6 table columns Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 table columns migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 table columns diff check: git diff --check -- backend/apps/license/table_columns.py backend/apps/license/tests/test_table_columns.py -> clean",
    "Phase 6 table columns security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license add template load verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings loaded license/add.html -> passed",
    "Phase 6 license add template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license add template migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license add template diff check: git diff --check -- backend/apps/license/templates/license/add.html -> clean",
    "Phase 6 license add template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license ajax-list template load verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings loaded license/ajax-list.html -> passed",
    "Phase 6 license ajax-list template render verification: blocked by NoReverseMatch for legacy URL name license-list, shared by pending legacy templates",
    "Phase 6 license ajax-list template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license ajax-list template migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license ajax-list template diff check: git diff --check -- backend/apps/license/templates/license/ajax-list.html -> clean",
    "Phase 6 license ajax-list template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license card template load verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings loaded license/card.html -> passed",
    "Phase 6 license card template full render verification: blocked by legacy URL names used by this server-rendered template",
    "Phase 6 license card template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license card template migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license card template diff check: git diff --check -- backend/apps/license/templates/license/card.html -> clean",
    "Phase 6 license card template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license consolidated template render verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings rendered license/consolidated.html with empty license_list -> passed",
    "Phase 6 license consolidated template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license consolidated template migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license consolidated template diff check: git diff --check -- backend/apps/license/templates/license/consolidated.html -> clean",
    "Phase 6 license consolidated template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license detail template render verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings rendered license/detail.html with empty export/import managers -> passed",
    "Phase 6 license detail template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license detail template migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license detail template diff check: git diff --check -- backend/apps/license/templates/license/detail.html -> clean",
    "Phase 6 license detail template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license formset template dependency analysis: repository-wide search found live include from backend/apps/license/templates/license/item_list_edit.html, so template was retained and audited",
    "Phase 6 license formset template render verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings rendered license/formset.html with a real Django formset -> passed",
    "Phase 6 license formset template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license formset template migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license formset template diff check: git diff --check -- backend/apps/license/templates/license/formset.html -> clean",
    "Phase 6 license formset template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license item_list_edit template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, or dynamic template-loading path for backend/apps/license/templates/license/item_list_edit.html; only stale license-item-update links remain",
    "Phase 6 license item_list_edit template removal: deleted verified-dead legacy Django template; no replacement dependency or migration required",
    "Phase 6 license item_list_edit post-removal dependency analysis: rg item_list_edit/license-item-update confirms no item_list_edit references; stale license-item-update links remain in blocked legacy card/DFIA templates",
    "Phase 6 license item_list_edit dependency graph update: backend/apps/license/templates/license/formset.html marked REQUIRES_RECHECK because its only known live include was removed",
    "Phase 6 license item_list_edit pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license item_list_edit Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license item_list_edit py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license item_list_edit Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license item_list_edit migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license item_list_edit compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license item_list_edit diff check: git diff --check -- backend/apps/license/templates/license/item_list_edit.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license item_list_edit security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license formset template recheck dependency analysis: after deleting backend/apps/license/templates/license/item_list_edit.html, repository-wide source search found no remaining live include, render path, template_name, email/PDF/report/export usage, command usage, or dynamic template loader for backend/apps/license/templates/license/formset.html",
    "Phase 6 license formset template removal: deleted verified-dead legacy Django partial; no replacement dependency or migration required",
    "Phase 6 license formset template pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license formset template Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license formset template py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license formset template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license formset template migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license formset template compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license formset template diff check: git diff --check -- backend/apps/license/templates/license/formset.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license formset template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license item_pdf template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/item_pdf.html",
    "Phase 6 license item_pdf template removal: deleted verified-dead legacy Django PDF template; no replacement dependency or migration required",
    "Phase 6 license item_pdf pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license item_pdf Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license item_pdf py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license item_pdf Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license item_pdf migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license item_pdf compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license item_pdf diff check: git diff --check -- backend/apps/license/templates/license/item_pdf.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license item_pdf security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license item_report template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/item_report.html; active item report code uses license/report_pdf_ITEM.html, license/report_pdf.html, API serializers, and React pages instead",
    "Phase 6 license item_report template removal: deleted verified-dead legacy Django PDF table template; no replacement dependency or migration required",
    "Phase 6 license item_report pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license item_report Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license item_report py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license item_report Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license item_report migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license item_report compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license item_report diff check: git diff --check -- backend/apps/license/templates/license/item_report.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license item_report security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license license_details template dependency analysis: repository-wide specific-template search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/license_details.html",
    "Phase 6 license license_details template removal: deleted verified-dead legacy Django detail template; no replacement dependency or migration required",
    "Phase 6 license license_details pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license license_details Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license license_details py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license license_details Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license license_details migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license license_details compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license license_details diff check: git diff --check -- backend/apps/license/templates/license/license_details.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license license_details security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license legacy list component dependency analysis: repository-wide search found no live render, template_name, include, command, URLConf, middleware, signal, test, or dynamic template-loading path for backend/apps/license/templates/license/list.html beyond its dead include chain to ajax-list.html and card.html",
    "Phase 6 license legacy list component removal: deleted verified-dead list.html, ajax-list.html, and card.html; cleared prior BLOCKED overrides because the templates no longer exist",
    "Phase 6 license legacy list component pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license legacy list component Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license legacy list component py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license legacy list component Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license legacy list component migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license legacy list component compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license legacy list component diff check: git diff --check -- backend/apps/license/templates/license/list.html backend/apps/license/templates/license/ajax-list.html backend/apps/license/templates/license/card.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license legacy list component security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license pdf template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/pdf.html; active report_service uses license/report_pdf.html instead",
    "Phase 6 license pdf template removal: deleted verified-dead legacy Django PDF summary template; no replacement dependency or migration required",
    "Phase 6 license pdf pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license pdf Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license pdf py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license pdf Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license pdf migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license pdf compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license pdf diff check: git diff --check -- backend/apps/license/templates/license/pdf.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license pdf security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license pdf_amend template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/pdf_amend.html",
    "Phase 6 license pdf_amend template removal: deleted verified-dead legacy amendment PDF template; no replacement dependency or migration required",
    "Phase 6 license pdf_amend pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license pdf_amend Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license pdf_amend py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license pdf_amend Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license pdf_amend migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license pdf_amend compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license pdf_amend diff check: git diff --check -- backend/apps/license/templates/license/pdf_amend.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license pdf_amend security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license pdf_consolidate template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/pdf_consolidate.html",
    "Phase 6 license pdf_consolidate template removal: deleted verified-dead legacy consolidated PDF template; no replacement dependency or migration required",
    "Phase 6 license pdf_consolidate pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license pdf_consolidate Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license pdf_consolidate py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license pdf_consolidate Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license pdf_consolidate migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license pdf_consolidate compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license pdf_consolidate diff check: git diff --check -- backend/apps/license/templates/license/pdf_consolidate.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license pdf_consolidate security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license pdf_ledger template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/pdf_ledger.html; active ledger PDF route uses apps.license.ledger_pdf.generate_license_ledger_pdf",
    "Phase 6 license pdf_ledger template removal: deleted verified-dead legacy ledger PDF template; no replacement dependency or migration required",
    "Phase 6 license pdf_ledger pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license pdf_ledger Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license pdf_ledger py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license pdf_ledger Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license pdf_ledger migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license pdf_ledger compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license pdf_ledger diff check: git diff --check -- backend/apps/license/templates/license/pdf_ledger.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license pdf_ledger security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license pdf_ledger_new template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/pdf_ledger_new.html; active ledger PDF route uses apps.license.ledger_pdf.generate_license_ledger_pdf",
    "Phase 6 license pdf_ledger_new template removal: deleted verified-dead legacy alternate ledger PDF template; no replacement dependency or migration required",
    "Phase 6 license pdf_ledger_new pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license pdf_ledger_new Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license pdf_ledger_new py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license pdf_ledger_new Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license pdf_ledger_new migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license pdf_ledger_new compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license pdf_ledger_new diff check: git diff --check -- backend/apps/license/templates/license/pdf_ledger_new.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license pdf_ledger_new security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license preimum_calc template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/preimum_calc.html; fuzzy search also found no premium_calc/preimum runtime path",
    "Phase 6 license preimum_calc template removal: deleted verified-dead legacy premium-calculation PDF template; no replacement dependency or migration required",
    "Phase 6 license preimum_calc pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license preimum_calc Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license preimum_calc py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license preimum_calc Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license preimum_calc migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license preimum_calc compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license preimum_calc diff check: git diff --check -- backend/apps/license/templates/license/preimum_calc.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license preimum_calc security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license report template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/report.html; stale item_report_list link existed only inside the deleted template",
    "Phase 6 license report template removal: deleted verified-dead legacy item-wise report index template; no replacement dependency or migration required",
    "Phase 6 license report pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license report Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license report py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license report Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license report migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license report compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license report diff check: git diff --check -- backend/apps/license/templates/license/report.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license report security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license report_form template dependency analysis: repository-wide search found no render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/license/templates/license/report_form.html; submit names item_report/item_generate are not used by live report API views",
    "Phase 6 license report_form template removal: deleted verified-dead legacy date-range report form template; no replacement dependency or migration required",
    "Phase 6 license report_form pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license report_form Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license report_form py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license report_form Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license report_form migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license report_form compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license report_form diff check: git diff --check -- backend/apps/license/templates/license/report_form.html docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license report_form security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license tests.py dependency analysis: repository-wide search found no imports or runtime references to backend/apps/license/tests.py; real License tests live under backend/apps/license/tests/",
    "Phase 6 license tests.py removal: deleted default empty Django test stub with unused TestCase import; no replacement dependency or migration required",
    "Phase 6 license tests.py pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license tests.py Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 6 license tests.py py_compile: .venv/bin/python -m py_compile docs/audit/build_audit_state.py -> passed",
    "Phase 6 license tests.py Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license tests.py migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license tests.py compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license tests.py diff check: git diff --check -- backend/apps/license/tests.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license tests.py security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license tests package init line audit: backend/apps/license/tests/__init__.py kept as package marker; removed non-functional module docstring",
    "Phase 6 license tests package init pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 300 passed, 2 skipped",
    "Phase 6 license tests package init Ruff: .venv/bin/ruff check backend/apps/license/tests/__init__.py docs/audit/build_audit_state.py -> clean",
    "Phase 6 license tests package init py_compile: .venv/bin/python -m py_compile backend/apps/license/tests/__init__.py docs/audit/build_audit_state.py -> passed",
    "Phase 6 license tests package init Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license tests package init migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license tests package init compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license tests package init diff check: git diff --check -- backend/apps/license/tests/__init__.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license tests package init security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license item_matcher line audit: reviewed all 877 lines, imports, item filter definitions, batch auto-linking, single-item matching, call sites in signals/serializers/management command, and edge paths for no norms/no matches/missing ItemNameModel",
    "Phase 6 license item_matcher improvement: match_import_item_to_items now resolves ItemNameModel names from the applicable norm instead of always using license_norm_classes[0], fixing multi-norm licenses where a later norm's filter matched",
    "Phase 6 license item_matcher performance cleanup: moved LicenseImportItemsModel import and base import-item queryset outside the inner loop; collect matched ids via values_list into a set instead of materializing model objects before re-querying",
    "Phase 6 license item_matcher regression tests: added backend/apps/license/tests/test_item_matcher.py covering multi-norm applicable norm matching and empty norm class behavior",
    "Phase 6 license item_matcher focused pytest: .venv/bin/python -m pytest backend/apps/license/tests/test_item_matcher.py -q -> 2 passed",
    "Phase 6 license item_matcher full pytest: .venv/bin/python -m pytest backend/apps/license/tests -q -> 302 passed, 2 skipped",
    "Phase 6 license item_matcher Ruff: .venv/bin/ruff check backend/apps/license/utils/item_matcher.py backend/apps/license/tests/test_item_matcher.py docs/audit/build_audit_state.py -> clean",
    "Phase 6 license item_matcher py_compile: .venv/bin/python -m py_compile backend/apps/license/utils/item_matcher.py backend/apps/license/tests/test_item_matcher.py docs/audit/build_audit_state.py -> passed",
    "Phase 6 license item_matcher Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license item_matcher migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license item_matcher compileall: .venv/bin/python -m compileall -q backend/apps/license -> passed",
    "Phase 6 license item_matcher diff check: git diff --check -- backend/apps/license/utils/item_matcher.py backend/apps/license/tests/test_item_matcher.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license item_matcher security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license_items line audit: reviewed all 61 lines, imports, serializer fields, queryset joins, filter/search/ordering settings, update serializer selection, router registration, React call sites, and existing API smoke tests",
    "Phase 6 license_items security hardening: added LicensePermission role gating, explicitly limited methods to GET/PUT/PATCH/HEAD/OPTIONS, and removed create/delete/TRACE from the advertised endpoint surface",
    "Phase 6 license_items validation hardening: made the simple serializer hs_code representation allow null and made dropdown label generation tolerate missing in-memory license references without breaking persisted FK behavior",
    "Phase 6 license_items performance review: retained select_related('license', 'hs_code') and prefetch_related('items') for list/update serializers to avoid N+1 reads on dropdown and PATCH responses",
    "Phase 6 license_items regression tests: added backend/apps/license/tests/test_license_items_view.py covering unauthenticated access, missing role, LICENSE_VIEWER list access with null hs_code, LICENSE_MANAGER patch, and create/delete 405 behavior",
    "Phase 6 license_items focused pytest: .venv/bin/python -m pytest backend/apps/license/tests/test_license_items_view.py -q -> 5 passed",
    "Phase 6 license_items impact pytest: .venv/bin/python -m pytest backend/apps/license/tests backend/tests/test_api_license.py backend/tests/test_all_conditions.py -q -> 385 passed, 2 skipped",
    "Phase 6 license_items Ruff: .venv/bin/ruff check backend/apps/license/views/license_items.py backend/apps/license/tests/test_license_items_view.py docs/audit/build_audit_state.py -> clean",
    "Phase 6 license_items py_compile: .venv/bin/python -m py_compile backend/apps/license/views/license_items.py backend/apps/license/tests/test_license_items_view.py -> passed",
    "Phase 6 license_items compileall: .venv/bin/python -m compileall -q backend/apps/license/views/license_items.py backend/apps/license/tests/test_license_items_view.py -> passed",
    "Phase 6 license_items import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported LicenseItemViewSet with LicensePermission and explicit method list -> passed",
    "Phase 6 license_items Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license_items migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license_items diff check: git diff --check -- backend/apps/license/views/license_items.py backend/apps/license/tests/test_license_items_view.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license_items security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 6 license_report line audit: reviewed all 179 lines, imports, query serializer, report action decorator, queryset filters, grouping loops, totals, response payload, and LicenseDetailsViewSet attachment",
    "Phase 6 license_report validation hardening: added ParleLicenseReportQuerySerializer with typed exporter, optional query booleans, trimmed notification input, and 400 responses for malformed query params",
    "Phase 6 license_report bug fix: OptionalQueryBooleanField prevents omitted query booleans from being interpreted as False, preserving prior optional filter semantics while validating provided values",
    "Phase 6 license_report serialization fix: purchase_status now returns primitive code and purchase_status_label instead of a model instance that JSONRenderer cannot serialize",
    "Phase 6 license_report performance fix: removed per-license export_license aggregate query, computes total CIF from prefetched export rows, and prefetches parent/child relations without excluding rows through unsafe split-table select_related joins",
    "Phase 6 license_report regression tests: added backend/apps/license/tests/test_license_report_view.py covering grouped JSON output, default Parle filtering, primitive purchase status fields, invalid query params, and boolean filter behavior",
    "Phase 6 license_report focused pytest: .venv/bin/python -m pytest backend/apps/license/tests/test_license_report_view.py -q -> 3 passed",
    "Phase 6 license_report impact pytest: .venv/bin/python -m pytest backend/apps/license/tests backend/tests/test_api_license.py backend/tests/test_all_conditions.py -q -> 388 passed, 2 skipped",
    "Phase 6 license_report Ruff: .venv/bin/ruff check backend/apps/license/views/license_report.py backend/apps/license/tests/test_license_report_view.py -> clean",
    "Phase 6 license_report py_compile: .venv/bin/python -m py_compile backend/apps/license/views/license_report.py backend/apps/license/tests/test_license_report_view.py -> passed",
    "Phase 6 license_report compileall: .venv/bin/python -m compileall -q backend/apps/license/views/license_report.py backend/apps/license/tests/test_license_report_view.py -> passed",
    "Phase 6 license_report import verification: cd backend; ../.venv/bin/python with DJANGO_SETTINGS_MODULE=lmanagement.settings and django.setup() imported report serializer/action; empty query params validate to {} -> passed",
    "Phase 6 license_report Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 6 license_report migration check: .venv/bin/python backend/manage.py makemigrations license --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 6 license_report diff check: git diff --check -- backend/apps/license/views/license_report.py backend/apps/license/tests/test_license_report_view.py docs/audit/build_audit_state.py docs/audit/phase-06-license-report.md -> clean",
    "Phase 6 license_report security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 pdf coordinate finder dependency analysis: repository-wide search found no live runtime references outside backend/apps/allotment/scripts/pdf_coordinate_finder.py and audit metadata; retained as standalone ReportLab helper",
    "Phase 7 pdf coordinate finder hardening: added argparse/pathlib CLI, validated positive grid spacing, protected existing output files by default, rejected directory targets, and removed unused pypdf import",
    "Phase 7 pdf coordinate finder regression: .venv/bin/python -m pytest backend/tests/test_pdf_coordinate_finder.py -q -> 7 passed",
    "Phase 7 pdf coordinate finder Ruff: .venv/bin/ruff check backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py -> clean",
    "Phase 7 pdf coordinate finder py_compile: .venv/bin/python -m py_compile backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py -> passed",
    "Phase 7 pdf coordinate finder compileall: .venv/bin/python -m compileall -q backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py -> passed",
    "Phase 7 pdf coordinate finder Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 7 pdf coordinate finder migration check: .venv/bin/python backend/manage.py makemigrations --check --dry-run -> no changes detected; sandboxed Postgres connection warning only",
    "Phase 7 pdf coordinate finder CLI help: .venv/bin/python backend/apps/allotment/scripts/pdf_coordinate_finder.py --help -> passed",
    "Phase 7 pdf coordinate finder import verification: imported DEFAULT_GRID_SPACING, create_coordinate_grid, and parse_args; --grid-spacing 25 --overwrite parsed successfully",
    "Phase 7 pdf coordinate finder audit-state verification: audit database marks script, test, and phase report COMPLETED after regenerating state",
    "Phase 7 pdf coordinate finder final Ruff: .venv/bin/ruff check backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py docs/audit/build_audit_state.py -> clean",
    "Phase 7 pdf coordinate finder final py_compile: .venv/bin/python -m py_compile backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py docs/audit/build_audit_state.py -> passed",
    "Phase 7 pdf coordinate finder diff check: git diff --check -- backend/apps/allotment/scripts/pdf_coordinate_finder.py backend/tests/test_pdf_coordinate_finder.py docs/audit/build_audit_state.py docs/audit/phase-07-reporting-report.md docs/audit/audit-database.json docs/audit/repository-knowledge-graph.json docs/audit/dashboard.md docs/audit/work-queue.md -> clean",
    "Phase 7 pdf coordinate finder security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 allotment download template dependency analysis: repository-wide search found no live render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path for backend/apps/allotment/templates/allotment/download.html",
    "Phase 7 allotment download template removal: deleted verified-dead legacy server-rendered export template; active allotment export uses DRF allotments/download action in backend/apps/allotment/views_export.py",
    "Phase 7 allotment download template security review: removed stale {{ df|safe }} rendering surface from dead template; stale allotment-download link in card.html remains for that file's own audit pass",
    "Phase 7 allotment download template audit-state verification: deleted template no longer appears in tracked source files after regenerating audit state",
    "Phase 7 allotment download template focused pytest: .venv/bin/python -m pytest backend/tests/test_api_allotment.py -q -> 7 passed",
    "Phase 7 allotment download template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 7 allotment download template migration check: .venv/bin/python backend/manage.py makemigrations --check --dry-run -> no changes detected; sandboxed PostgreSQL connection warning only",
    "Phase 7 allotment download template Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 7 allotment pdf_base template dependency analysis: repository-wide search found no live direct render path; only backend/apps/allotment/templates/allotment/send.html extended it",
    "Phase 7 allotment send template dependency analysis: repository-wide search found no live render, template_name, include, email/PDF/report/export, command, URLConf, middleware, signal, test, documentation runtime, or dynamic template-loading path",
    "Phase 7 allotment pdf_base template removal: deleted verified-dead legacy PDF base and recursively removed its orphaned send.html child template",
    "Phase 7 allotment pdf_base template audit-state verification: deleted pdf_base.html and send.html no longer appear in tracked source files after regenerating audit state",
    "Phase 7 allotment pdf_base template focused pytest: .venv/bin/python -m pytest backend/tests/test_api_allotment.py -q -> 7 passed",
    "Phase 7 allotment pdf_base template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 7 allotment pdf_base template migration check: .venv/bin/python backend/manage.py makemigrations --check --dry-run -> no changes detected; sandboxed PostgreSQL connection warning only",
    "Phase 7 allotment pdf_base template Ruff: .venv/bin/ruff check docs/audit/build_audit_state.py -> clean",
    "Phase 7 allotment grouped export API line audit: reviewed all 695 lines, imports, endpoint args, queryset shaping, PDF builder, XLSX builder, grouping logic, dependency fallbacks, response headers, and null/default handling",
    "Phase 7 allotment grouped export API hardening: normalized _export/type inputs, returned 400 before export work for unsupported formats, returned 503 for missing openpyxl/reportlab, preserved Decimal values in grouping, and removed unused ReportLab imports",
    "Phase 7 allotment grouped export API performance: changed company/port relationship loading to select_related and added nested allocation/license/exporter/port prefetches used by grouping",
    "Phase 7 allotment grouped export API regression: .venv/bin/python -m pytest backend/tests/test_api_allotment.py -q -> 11 passed",
    "Phase 7 allotment grouped export API selected Ruff: .venv/bin/ruff check backend/apps/allotment/views_export.py backend/tests/test_api_allotment.py --select F401,F821,F811,E741,F841,B007,B904,UP035,UP006,UP045 -> clean",
    "Phase 7 allotment grouped export API Ruff: .venv/bin/ruff check backend/apps/allotment/views_export.py backend/tests/test_api_allotment.py -> clean",
    "Phase 7 allotment grouped export API py_compile: .venv/bin/python -m py_compile backend/apps/allotment/views_export.py backend/tests/test_api_allotment.py -> passed",
    "Phase 7 allotment grouped export API compileall: .venv/bin/python -m compileall -q backend/apps/allotment/views_export.py backend/tests/test_api_allotment.py -> passed",
    "Phase 7 allotment grouped export API Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 7 allotment grouped export API migration check: .venv/bin/python backend/manage.py makemigrations --check --dry-run -> no changes detected; sandboxed PostgreSQL connection warning only",
    "Phase 7 allotment grouped export API import verification: Django setup imported AllotmentViewSet with download_grouped_export and _group_allotments attached",
    "Phase 7 allotment grouped export API security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 BOE pending-bill template dependency analysis: repository-wide search found download.html and download_port.html referenced only by unused backend/apps/bill_of_entry/views/download_views.py and audit metadata; bill_of_entry URLConf exposes only DRF routes and parse-pdf",
    "Phase 7 BOE pending-bill template removal: deleted verified-dead legacy PDF templates and their unreachable DownloadPendingBillView/DownloadPortView module; cleaned stale commented re-export references from views package",
    "Phase 7 BOE pending-bill template verification: remaining exact-reference scan after deletion found only generated audit metadata before state regeneration",
    "Phase 7 BOE pending-bill template focused pytest: .venv/bin/python -m pytest backend/tests/test_api_boe.py -q -> 7 passed",
    "Phase 7 BOE pending-bill template Ruff: .venv/bin/ruff check backend/apps/bill_of_entry/views/__init__.py docs/audit/build_audit_state.py -> clean",
    "Phase 7 BOE pending-bill template py_compile: .venv/bin/python -m py_compile backend/apps/bill_of_entry/views/__init__.py docs/audit/build_audit_state.py -> passed",
    "Phase 7 BOE pending-bill template compileall: .venv/bin/python -m compileall -q backend/apps/bill_of_entry/views docs/audit/build_audit_state.py -> passed",
    "Phase 7 BOE pending-bill template Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 7 BOE pending-bill template migration check: .venv/bin/python backend/manage.py makemigrations --check --dry-run -> no changes detected; sandboxed PostgreSQL connection warning only",
    "Phase 7 BOE pending-bill template import/template verification: reversed active BOE API routes and confirmed removed legacy templates no longer resolve",
    "Phase 7 BOE pending-bill template diff check: git diff --check for scoped BOE removal and audit artifacts -> clean",
    "Phase 7 BOE pending-bill template security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 BOE export API line audit: reviewed all 820 lines, endpoint parameter handling, queryset shaping, PDF builder, grouped XLSX builder, port XLSX builder, grouping helper, optional dependency paths, response headers, and null/default handling",
    "Phase 7 BOE export API hardening: normalized _export input, rejected unsupported formats before query/export work, returned 503 for missing openpyxl/reportlab, guarded nullable license_date, and preserved Decimal values in grouping",
    "Phase 7 BOE export API performance: cleared inherited prefetches before applying export-specific select_related/Prefetch plan for RowDetails -> license/exporter/port/hs_code, avoiding duplicate-prefetch runtime failure and N+1 related lookups",
    "Phase 7 BOE export API regression: .venv/bin/python -m pytest backend/tests/test_api_boe.py -q -> 12 passed",
    "Phase 7 BOE export API Ruff: .venv/bin/ruff check backend/apps/bill_of_entry/views_export.py backend/tests/test_api_boe.py -> clean",
    "Phase 7 BOE export API py_compile: .venv/bin/python -m py_compile backend/apps/bill_of_entry/views_export.py backend/tests/test_api_boe.py -> passed",
    "Phase 7 BOE export API compileall: .venv/bin/python -m compileall -q backend/apps/bill_of_entry/views_export.py backend/tests/test_api_boe.py -> passed",
    "Phase 7 BOE export API Django check: .venv/bin/python backend/manage.py check -> no issues",
    "Phase 7 BOE export API migration check: .venv/bin/python backend/manage.py makemigrations --check --dry-run -> no changes detected; sandboxed PostgreSQL connection warning only",
    "Phase 7 BOE export API import verification: Django setup imported BillOfEntryViewSet with export_bill_of_entries and _group_boe attached; export route reverses to /api/bill-of-entries/export/",
    "Phase 7 BOE export API security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 shared.pdf package marker audit: reviewed 0-line backend/shared/pdf/__init__.py; retained empty package marker because shared.pdf.builders is imported by license PDF exporter code",
    "Phase 7 shared.pdf package marker verification: import shared.pdf and shared.pdf.builders passed; Ruff, py_compile, and compileall passed",
    "Phase 7 PDF viewer guide audit: rewrote stale PDF viewer implementation guide to match current TypeScript route/component/helper paths and active blob preview behavior",
    "Phase 7 PDF viewer security hardening: PDFViewer now rejects empty, absolute, protocol-relative, backslash-containing, and control-character url query values before Axios requests",
    "Phase 7 PDF viewer regression: npm test -- PDFViewer.test.tsx -> 3 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/PDFViewer.tsx src/pages/PDFViewer.test.tsx -> passed; npm run build -> passed",
    "Phase 7 UX/UI audit report dependency analysis: repository-wide search found docs/guides/UX_UI_AUDIT_REPORT.md referenced only by docs/README.md and audit metadata; content was stale JSX-era planning documentation and not a live reporting/export path",
    "Phase 7 UX/UI audit report removal: deleted verified-dead stale guide and removed its docs/README.md index entry instead of carrying obsolete unresolved future-action content in the active audit knowledge base",
    "Phase 7 LicenseExportPanel audit: reviewed shared active/expiring license Excel export component, props, days input, endpoint/filename callbacks, blob download path, loading state, toast error path, and feature rendering",
    "Phase 7 LicenseExportPanel hardening: added typed props, normalized/clamped days to 1-365, stable input/help IDs, shared authenticated download helper usage, and focused regression tests",
    "Phase 7 LicenseExportPanel verification: npm test -- LicenseExportPanel.test.tsx -> 3 passed; npm run typecheck -> passed; npm run lint -- --quiet src/components/reports/LicenseExportPanel.tsx src/components/reports/LicenseExportPanel.test.tsx -> passed; npm run build -> passed",
    "Phase 7 ActiveLicenses page audit: reviewed React report wrapper, shared LicenseExportPanel integration, endpoint and filename callbacks, feature copy, route references, and active-license export semantics",
    "Phase 7 ActiveLicenses hardening: removed stale hard-coded 2026/2027 copy and replaced symbolic date phrasing with accessible plain-language lookback text",
    "Phase 7 ActiveLicenses regression: added frontend/src/pages/reports/ActiveLicenses.test.tsx covering visible copy, default days, stale-year absence, and active-license export URL/filename generation",
    "Phase 7 ActiveLicenses verification: npm test -- ActiveLicenses.test.tsx -> 2 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/ActiveLicenses.tsx src/pages/reports/ActiveLicenses.test.tsx -> passed; npm run build -> passed",
    "Phase 7 DownloadLicense audit: reviewed React report page, status report GET path, bulk balance Excel POST path, blob download cleanup, manual license parsing, date-range input, route references, and accessibility wiring",
    "Phase 7 DownloadLicense hardening: added day normalization to 1-3650, manual license-number trim/dedupe, malformed report-row filtering, delayed object URL revocation, textarea labels/help text, and aria-pressed status controls",
    "Phase 7 DownloadLicense regression: added frontend/src/pages/reports/DownloadLicense.test.tsx covering helper boundaries, dedupe, empty input, malformed report rows, active endpoint export, and expiring endpoint export",
    "Phase 7 DownloadLicense verification: npm test -- DownloadLicense.test.tsx -> 6 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/DownloadLicense.tsx src/pages/reports/DownloadLicense.test.tsx -> passed; npm run build -> passed",
    "Phase 7 ExpiringLicenses page audit: reviewed React report wrapper, shared LicenseExportPanel integration, endpoint and filename callbacks, feature copy, route references, and expiring-license export semantics",
    "Phase 7 ExpiringLicenses regression: added frontend/src/pages/reports/ExpiringLicenses.test.tsx covering rendered copy, default lookahead days, feature copy, and expiring-license export URL/filename generation",
    "Phase 7 ExpiringLicenses verification: npm test -- ExpiringLicenses.test.tsx -> 2 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/ExpiringLicenses.tsx src/pages/reports/ExpiringLicenses.test.tsx -> passed; npm run build -> passed",
    "Phase 7 ItemPivotFilters audit: reviewed filter props, min-balance parsing, license status select, purchase-status multi-select, expiry date inputs, company include/exclude selectors, active-filter chips, clear action, and parent ItemPivotReport contract",
    "Phase 7 ItemPivotFilters hardening: added typed select options, defensive min-balance normalization, stable labels for native controls, SSR-safe react-select portal target, boolean coercion for string-backed active-filter expressions, and focused tests",
    "Phase 7 ItemPivotFilters verification: npm test -- ItemPivotFilters.test.tsx -> 4 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/ItemPivotFilters.tsx src/pages/reports/ItemPivotFilters.test.tsx -> passed; npm run build -> passed",
    "Phase 7 ItemPivotReport audit: reviewed 1478-line React report page, report URL construction, JSON/excel export paths, balance update polling, modal document opening, numeric summary aggregation, table rendering dependencies, and parent/child filter contract",
    "Phase 7 ItemPivotReport hardening: replaced string-concatenated query URLs with URLSearchParams helper, normalized malformed numeric values before aggregation, reused authenticated document download helper, removed direct localStorage auth header access, guarded missing task ids, and delegated excel download blob handling to shared openAuthedFile",
    "Phase 7 ItemPivotReport regression: added frontend/src/pages/reports/ItemPivotReport.test.ts covering encoded URL construction, blank optional filters, malformed numeric fallbacks, and non-finite numeric protection",
    "Phase 7 ItemPivotReport verification: npm test -- ItemPivotReport.test.ts -> 3 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/ItemPivotReport.tsx src/pages/reports/ItemPivotReport.test.ts -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning",
    "Phase 7 ItemPivotReport commit: 91fadfcad93f027592594783c6387dca8d88e9ab at 2026-07-16T15:19:38+05:30, fix(reports): harden item pivot report",
    "Phase 7 ItemReport audit: reviewed 1231-line React item report page, report URL construction, JSON/excel export paths, item-name inline edit refresh, filter controls, authenticated document opening, option loading fallbacks, and report table rendering",
    "Phase 7 ItemReport hardening: replaced duplicated string-concatenated report URLs with URLSearchParams helper, normalized malformed numeric filters, reused shared openAuthedFile for Excel export, removed console logging from option-load fallback paths, deduplicated purchase/norm options, and added stable labels/input IDs for filter controls",
    "Phase 7 ItemReport regression: added frontend/src/pages/reports/ItemReport.test.ts covering encoded URL construction, blank optional filters, malformed numeric fallbacks, value normalization, Unicode-safe query encoding, and non-finite numeric protection",
    "Phase 7 ItemReport verification: npm test -- ItemReport.test.ts -> 3 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/ItemReport.tsx src/pages/reports/ItemReport.test.ts -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; git diff --check scoped to ItemReport files -> clean; py_compile not applicable to TSX/TS frontend source",
    "Phase 7 ItemReport security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 ItemReport commit: 1248ff802868a5d899b7944d11453456a86c6212 at 2026-07-16T15:24:02+05:30, fix(reports): harden item report",
    "Phase 7 NormCardGrid audit: reviewed 152-line React norm selector grid, props, malformed norm handling, duplicate key risk, active selection behavior, loading indicator, icon accessibility, empty-state rendering, and parent ItemPivotReport contract",
    "Phase 7 NormCardGrid hardening: added typed norm input/normalized card model, filtered null/blank objects missing norm_class, deduplicated duplicate norm classes, removed negative letter spacing, added aria-pressed to norm buttons, and hid decorative icons from assistive tech",
    "Phase 7 NormCardGrid regression: added frontend/src/pages/reports/NormCardGrid.test.tsx covering malformed/blank/duplicate normalization, active button accessibility, changed-norm report reset, and reselecting the active norm without clearing data",
    "Phase 7 NormCardGrid verification: npm test -- NormCardGrid.test.tsx -> 3 passed after fixing object-without-norm_class normalization; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/NormCardGrid.tsx src/pages/reports/NormCardGrid.test.tsx -> passed; npm run build -> passed; Django check -> exit 0 with staticfiles.W004 frontend/dist/assets warning; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 NormCardGrid security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 NormCardGrid commit: 4b20a546b0b8c76e110237c1e155482ccc72a0ca at 2026-07-16T15:27:02+05:30, fix(reports): harden norm card grid",
    "Phase 7 SionE1 audit: reviewed 10-line React wrapper, SionNormReport dependency, route registration, fixed sionNorm prop, title prop, render path, and absence of local validation/query/export state",
    "Phase 7 SionE1 hardening: no runtime code change required; wrapper is intentionally a thin typed route adapter to shared SionNormReport",
    "Phase 7 SionE1 regression: added frontend/src/pages/reports/SionE1.test.tsx mocking SionNormReport and asserting the E1 norm/title contract",
    "Phase 7 SionE1 verification: npm test -- SionE1.test.tsx -> 1 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/SionE1.tsx src/pages/reports/SionE1.test.tsx -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 SionE1 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 SionE1 commit: ede878cce8184292ee2b142c5990af29b34e881e at 2026-07-16T15:29:16+05:30, test(reports): cover sion e1 wrapper",
    "Phase 7 SionE126 audit: reviewed 10-line React wrapper, SionNormReport dependency, route registration, fixed sionNorm prop, title prop, render path, and absence of local validation/query/export state",
    "Phase 7 SionE126 hardening: no runtime code change required; wrapper is intentionally a thin route adapter to shared SionNormReport",
    "Phase 7 SionE126 regression: added frontend/src/pages/reports/SionE126.test.tsx mocking SionNormReport and asserting the E126 norm/title contract",
    "Phase 7 SionE126 verification: npm test -- SionE126.test.tsx -> 1 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/SionE126.tsx src/pages/reports/SionE126.test.tsx -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 SionE126 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 SionE126 commit: 28f1638598923076d478d8e9349ce78a1c43b7c1 at 2026-07-16T15:31:14+05:30, test(reports): cover sion e126 wrapper",
    "Phase 7 SionE132 audit: reviewed 10-line React wrapper, SionNormReport dependency, route registration, fixed sionNorm prop, title prop, render path, and absence of local validation/query/export state",
    "Phase 7 SionE132 hardening: no runtime code change required; wrapper is intentionally a thin route adapter to shared SionNormReport",
    "Phase 7 SionE132 regression: added frontend/src/pages/reports/SionE132.test.tsx mocking SionNormReport and asserting the E132 norm/title contract",
    "Phase 7 SionE132 verification: npm test -- SionE132.test.tsx -> 1 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/SionE132.tsx src/pages/reports/SionE132.test.tsx -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 SionE132 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 SionE132 commit: bb40f71130e8c5090ae682859dbea5da2f2f62bc at 2026-07-16T15:33:00+05:30, test(reports): cover sion e132 wrapper",
    "Phase 7 SionE5 audit: reviewed 10-line React wrapper, SionNormReport dependency, route registration, fixed sionNorm prop, title prop, render path, and absence of local validation/query/export state",
    "Phase 7 SionE5 hardening: no runtime code change required; wrapper is intentionally a thin route adapter to shared SionNormReport",
    "Phase 7 SionE5 regression: added frontend/src/pages/reports/SionE5.test.tsx mocking SionNormReport and asserting the E5 norm/title contract",
    "Phase 7 SionE5 verification: npm test -- SionE5.test.tsx -> 1 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/SionE5.tsx src/pages/reports/SionE5.test.tsx -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 SionE5 security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 SionE5 commit: 4574c8d35370e8547f6dd1386ce62e4457e34b58 at 2026-07-16T15:34:56+05:30, test(reports): cover sion e5 wrapper",
    "Phase 7 SionNormReport audit: reviewed 408-line shared React report implementation, API query construction, filter state, effect cleanup, malformed response handling, numeric/date formatting, dense table rendering, notification grouping, totals rows, loading/empty states, and wrapper contracts",
    "Phase 7 SionNormReport hardening: added typed props/filters, centralized buildSionReportPath, normalized boolean filters, rejected NaN/infinite number output, guarded malformed groups/notifications/licenses/totals, prevented post-unmount state updates, encoded license IDs in links, added fieldset/legend radio groups, and replaced index-only notification keys",
    "Phase 7 SionNormReport regression: added frontend/src/pages/reports/SionNormReport.test.tsx covering helper normalization, malformed API groups, finite number formatting, default fetch path, and radio-triggered reload paths",
    "Phase 7 SionNormReport verification: npm test -- SionNormReport.test.tsx -> 5 passed; npm run typecheck -> passed; npm run lint -- --quiet src/pages/reports/SionNormReport.tsx src/pages/reports/SionNormReport.test.tsx -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 SionNormReport security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 SionNormReport commit: 78e9c91eebad9007552cd95e7519dca062021b08 at 2026-07-16T15:38:09+05:30, fix(reports): harden sion norm report",
    "Phase 7 documentDownload audit: reviewed shared authenticated blob download helper, protected media path normalization, report/export download callers, object URL lifecycle, new-tab/download branches, and unsafe external URL risk",
    "Phase 7 documentDownload hardening: added normalizeAuthedFilePath, rejected blank absolute protocol-relative backslash and control-character paths before Axios requests, trimmed media paths, supported protocol-relative media URLs by stripping origin, and rejected empty/unsafe media paths",
    "Phase 7 documentDownload regression: expanded frontend/src/utils/documentDownload.test.ts to cover unsafe media paths, safe relative report paths, absolute/protocol-relative rejection, backslash rejection, and pre-request failure for unsafe openAuthedFile paths",
    "Phase 7 documentDownload verification: npm test -- documentDownload.test.ts -> 8 passed; npm run typecheck -> passed; npm run lint -- --quiet src/utils/documentDownload.ts src/utils/documentDownload.test.ts -> passed; npm run build -> passed; Django check -> no issues; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 documentDownload security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 documentDownload commit: bf5ad0010a89381311d2542d3eb4c613dbed68fa at 2026-07-16T15:41:27+05:30, fix(reports): validate authenticated download paths",
    "Phase 7 pdfPreview audit: reviewed shared PDF blob preview wrapper, popup-blocked path, object URL lifecycle, wrapper HTML construction, title/download filename handling, and report/export callers",
    "Phase 7 pdfPreview hardening: exported and tested filename/HTML helpers, normalized blank unsafe control-character and overlong PDF names, escaped title/download attributes, removed non-ASCII download label, and kept blocked-popup URL cleanup",
    "Phase 7 pdfPreview regression: added frontend/src/utils/pdfPreview.test.ts covering blank/unsafe filenames, HTML-sensitive escaping, popup-blocked cleanup, and escaped wrapper HTML",
    "Phase 7 pdfPreview verification: npm test -- pdfPreview.test.ts -> 4 passed; npm run typecheck -> passed; npm run lint -- --quiet src/utils/pdfPreview.js src/utils/pdfPreview.test.ts -> passed; npm run build -> passed; Django check -> exit 0 with staticfiles.W004 frontend/dist/assets warning; makemigrations --check --dry-run -> no changes detected with sandboxed PostgreSQL warning; compileall and scoped git diff --check -> clean",
    "Phase 7 pdfPreview security tooling check: .venv/bin contains no bandit, pip-audit, safety, or semgrep executable -> blocked",
    "Phase 7 pdfPreview commit: 3ad2061986783d8f0a3cc98fcd7771f586af65a5 at 2026-07-16T15:44:54+05:30, fix(reports): harden pdf preview wrapper",
    "Ruff F821 undefined-name sweep: clean",
    "Previous Ruff selected F811/E741 baseline: 23 findings, now resolved",
    "Ruff full baseline: 547 findings remain",
]

WORK_QUEUE = [
    {
        "id": "P7-REPORTING-EXPORTS-AUDIT",
        "priority": 1,
        "stream": "Reporting & Exports",
        "status": "PENDING",
        "title": "Continue Phase 7 Reporting & Exports audit from the next pending report/export file",
        "impact": "Phase 6 License is frozen; continue with reporting, export, PDF, Excel, CSV, download, and report-helper files from the dependency graph.",
        "verification": "Run focused backend tests, Ruff, py_compile, compileall, Django check, migration checks, static analysis, and available security tooling after each completed file.",
    },
]


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line for line in result.stdout.splitlines() if line]


def exclusion_reason(path: str) -> str | None:
    if path in GENERATED_AUDIT_FILES:
        return "generated audit state"
    if any(path == prefix or path.startswith(prefix) for prefix in EXCLUDED_PATH_PREFIXES):
        return "generated index, vendor bundle, or large generated PDF"
    parts = set(Path(path).parts)
    excluded_parts = parts & EXCLUDED_DIR_PARTS
    if excluded_parts:
        return f"excluded directory: {sorted(excluded_parts)[0]}"

    path_obj = Path(path)
    if path_obj.name in SOURCE_FILENAMES:
        return None
    if path_obj.name == ".DS_Store":
        return "OS metadata"
    suffix = path_obj.suffix.lower()
    if suffix in BINARY_OR_GENERATED_EXTENSIONS:
        return "binary, log, or generated artifact"
    if suffix in SOURCE_EXTENSIONS:
        return None
    if path_obj.name.startswith(".env."):
        return None
    return "non-source artifact"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_symbols() -> dict[str, list[dict[str, Any]]]:
    rows: dict[str, list[dict[str, Any]]] = {}
    path = CLAUDE_INDEX / "symbols.tsv"
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        name, kind, file_path, line_no = parts
        if line_no == "line":
            continue
        rows.setdefault(file_path, []).append(
            {"name": name, "kind": kind, "line": int(line_no)}
        )
    return rows


def load_edge_tsv(name: str) -> dict[str, list[str]]:
    edges: dict[str, list[str]] = {}
    path = CLAUDE_INDEX / name
    if not path.exists():
        return edges
    for line in path.read_text(encoding="utf-8").splitlines():
        source, _, target = line.partition("\t")
        if source and target:
            edges.setdefault(source, []).append(target)
    return edges


def count_pattern(pattern: str, text: str) -> int:
    return len(re.findall(pattern, text, flags=re.MULTILINE))


def language_for(path: str, previous: dict[str, Any] | None) -> str:
    if previous and previous.get("lang"):
        return previous["lang"]
    suffix = Path(path).suffix.lower()
    return {
        ".css": "css",
        ".html": "html",
        ".js": "javascript",
        ".jsx": "javascript-react",
        ".json": "json",
        ".md": "markdown",
        ".py": "python",
        ".sh": "shell",
        ".sql": "sql",
        ".ts": "typescript",
        ".tsx": "typescript-react",
        ".yaml": "yaml",
        ".yml": "yaml",
    }.get(suffix, "other")


def module_for(path: str) -> str:
    parts = Path(path).parts
    if not parts:
        return "(root)"
    if parts[0] == "backend" and len(parts) >= 3 and parts[1] == "apps":
        return f"backend/apps/{parts[2]}"
    if parts[0] == "frontend" and len(parts) >= 3 and parts[1] == "src":
        return f"frontend/src/{parts[2]}"
    if parts[0] in {"docs", "ledgers", "master-data-service", "mds-client", "scripts"}:
        return parts[0]
    return parts[0]


def score_record(
    status: str,
    changed: bool,
    lines: int,
    imports: int,
    functions: int,
    classes: int,
) -> dict[str, int]:
    size_pressure = min(35, lines // 80)
    coupling_pressure = min(25, imports * 2)
    symbol_pressure = min(20, functions + classes * 2)
    changed_pressure = 10 if changed and status != "COMPLETED" else 0
    debt = min(100, size_pressure + coupling_pressure + symbol_pressure + changed_pressure)
    return {
        "complexity": min(100, lines // 100 + functions * 2 + classes * 3),
        "technical_debt_score": debt,
        "duplicate_score": 0,
        "performance_score": max(0, 100 - min(70, lines // 120)),
        "security_score": 100 if status == "COMPLETED" else 80,
        "maintainability_score": max(0, 100 - debt),
        "readability_score": max(0, 100 - min(80, size_pressure + symbol_pressure)),
    }


def build_database() -> dict[str, Any]:
    manifest = load_json(CLAUDE_INDEX / "manifest.json", {"files": {}})
    previous_files: dict[str, Any] = manifest.get("files", {})
    symbols = load_symbols()
    imports_graph = load_edge_tsv("imports.tsv")
    dependents_graph = load_edge_tsv("dependents.tsv")
    previous_audit = load_json(AUDIT_ROOT / "audit-database.json", {"files": {}})
    previous_records: dict[str, Any] = previous_audit.get("files", {})

    all_file_paths = sorted(
        path
        for path in run_git(["ls-files", "--cached", "--others", "--exclude-standard"])
        if (REPO_ROOT / path).exists()
    )
    excluded_files = {
        path: {"audit_status": "IGNORED", "reason": reason}
        for path in all_file_paths
        if (reason := exclusion_reason(path))
    }
    file_paths = [path for path in all_file_paths if path not in excluded_files]
    git_modified = set(run_git(["diff", "--name-only"]))
    git_untracked = set(run_git(["ls-files", "--others", "--exclude-standard"]))
    now = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat()

    files: dict[str, Any] = {}
    module_rollups: dict[str, dict[str, int]] = {}
    changed_files: set[str] = set()
    impacted_files: set[str] = set()

    for path in file_paths:
        abs_path = REPO_ROOT / path
        current_sha = sha256(abs_path)
        previous = previous_files.get(path)
        previous_sha = previous.get("sha") if previous else None
        changed_since_index = previous_sha is not None and previous_sha != current_sha
        directly_changed = path in git_modified or path in git_untracked
        previous_record = previous_records.get(path, {})

        if path in BLOCKED_VERIFIED_FILES:
            status = "BLOCKED"
            audited_at = now
        elif path in REQUIRES_RECHECK_FILES:
            status = "REQUIRES_RECHECK"
            audited_at = None
        elif path in COMPLETED_VERIFIED_FILES:
            status = "COMPLETED"
            audited_at = now
        elif (
            previous_record.get("audit_status") == "COMPLETED"
            and previous_record.get("file_checksum") == current_sha
        ):
            status = "COMPLETED"
            audited_at = previous_record.get("last_audit_timestamp")
        elif directly_changed:
            status = "CHANGED"
            audited_at = previous_record.get("last_audit_timestamp")
        else:
            status = previous_record.get("audit_status", "NOT_STARTED")
            if status not in {
                "BLOCKED",
                "CHANGED",
                "COMPLETED",
                "IGNORED",
                "IN_PROGRESS",
                "NOT_STARTED",
                "REQUIRES_RECHECK",
            }:
                status = "NOT_STARTED"
            audited_at = previous_record.get("last_audit_timestamp")

        text = read_text(abs_path)
        stat = abs_path.stat()
        lines = 0 if not text else text.count("\n") + (0 if text.endswith("\n") else 1)
        file_symbols = symbols.get(path, previous.get("symbols", []) if previous else [])
        if file_symbols and isinstance(file_symbols[0], list):
            normalized_symbols = [
                {"name": item[0], "kind": item[1], "line": item[2]}
                for item in file_symbols
            ]
        else:
            normalized_symbols = file_symbols

        import_count = len(imports_graph.get(path, previous.get("imports", []) if previous else []))
        imported_modules = imports_graph.get(path, previous.get("imports", []) if previous else [])
        function_count = sum(
            1
            for symbol in normalized_symbols
            if symbol["kind"] in {"export:func", "func", "hook", "method"}
        )
        class_count = sum(
            1
            for symbol in normalized_symbols
            if symbol["kind"]
            in {"class", "component", "export:component", "model", "serializer", "view"}
        )
        if not normalized_symbols:
            function_count += count_pattern(r"^\s*(def|async def|function)\s+\w+", text)
            class_count += count_pattern(r"^\s*class\s+\w+", text)
        symbol_fingerprint = hashlib.sha256(
            json.dumps(normalized_symbols, sort_keys=True).encode("utf-8")
        ).hexdigest()

        scores = score_record(
            status, changed_since_index, lines, import_count, function_count, class_count
        )
        module = module_for(path)
        rollup = module_rollups.setdefault(
            module,
            {
                "blocked": 0,
                "changed": 0,
                "completed": 0,
                "files": 0,
                "in_progress": 0,
                "lines": 0,
                "not_started": 0,
                "requires_recheck": 0,
            },
        )
        rollup["files"] += 1
        rollup["lines"] += lines
        rollup[status.lower()] = rollup.get(status.lower(), 0) + 1

        if directly_changed:
            changed_files.add(path)
            impacted_files.add(path)
            impacted_files.update(imports_graph.get(path, []))
            impacted_files.update(dependents_graph.get(path, []))

        files[path] = {
            "file_checksum": current_sha,
            "file_fingerprint": {
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "symbol_checksum": symbol_fingerprint,
            },
            "index_checksum_mismatch": changed_since_index,
            "previous_index_checksum": previous_sha,
            "last_audit_timestamp": audited_at,
            "audit_status": status,
            "language": language_for(path, previous),
            "module": module,
            "imported_modules": imported_modules,
            "exported_symbols": [symbol["name"] for symbol in normalized_symbols],
            "todo_count": len(re.findall(r"\bTODO\b", text)),
            "fixme_count": len(re.findall(r"\bFIXME\b", text)),
            "total_lines": lines,
            "total_functions": function_count,
            "total_classes": class_count,
            "total_imports": import_count,
            **scores,
        }

    for impacted_path in sorted(impacted_files):
        if impacted_path in COMPLETED_VERIFIED_FILES or impacted_path in BLOCKED_VERIFIED_FILES:
            continue
        if impacted_path in files and files[impacted_path]["audit_status"] == "COMPLETED":
            files[impacted_path]["audit_status"] = "REQUIRES_RECHECK"
            files[impacted_path]["last_audit_timestamp"] = None
            module = files[impacted_path]["module"]
            module_rollups[module]["completed"] -= 1
            module_rollups[module]["requires_recheck"] += 1

    totals = {
        "blocked": sum(1 for record in files.values() if record["audit_status"] == "BLOCKED"),
        "changed": sum(1 for record in files.values() if record["audit_status"] == "CHANGED"),
        "completed": sum(1 for record in files.values() if record["audit_status"] == "COMPLETED"),
        "ignored": len(excluded_files),
        "in_progress": sum(
            1 for record in files.values() if record["audit_status"] == "IN_PROGRESS"
        ),
        "files": len(files),
        "lines": sum(record["total_lines"] for record in files.values()),
        "not_started": sum(1 for record in files.values() if record["audit_status"] == "NOT_STARTED"),
        "requires_recheck": sum(
            1 for record in files.values() if record["audit_status"] == "REQUIRES_RECHECK"
        ),
        "todo": sum(record["todo_count"] for record in files.values()),
        "fixme": sum(record["fixme_count"] for record in files.values()),
    }
    totals["audited_lines"] = sum(
        record["total_lines"]
        for record in files.values()
        if record["audit_status"] == "COMPLETED"
    )
    totals["remaining_lines"] = totals["lines"] - totals["audited_lines"]

    return {
        "schema_version": 1,
        "generated_at": now,
        "repository_metadata": {
            "branch": run_git(["branch", "--show-current"])[0],
            "head": run_git(["rev-parse", "--short", "HEAD"])[0],
            "working_tree": "dirty" if git_modified or git_untracked else "clean",
        },
        "repository_inventory": {
            "source_files": len(files),
            "excluded_files": len(excluded_files),
            "inventory_rule": "Only source, tests, configs, migrations, scripts, and documentation are audited.",
        },
        "source_index": {
            "generated_file_count": manifest.get("file_count"),
            "path": ".claude/index/manifest.json",
            "purpose": "Seed graph/checksum state; this audit layer tracks review progress.",
        },
        "status_policy": {
            "BLOCKED": "Cannot be completed without user input or an external dependency.",
            "CHANGED": "File contents changed directly and need audit or verification.",
            "COMPLETED": "Reviewed, changed if needed, and verified for the relevant gates.",
            "IGNORED": "Excluded from source audit by inventory rules and tracked separately.",
            "IN_PROGRESS": "Currently being reviewed or refactored.",
            "NOT_STARTED": "Known in repository but not yet audited in this Codex audit pass.",
            "REQUIRES_RECHECK": "Needs recheck because imports, dependents, exported symbols, public API, or related tests changed.",
        },
        "totals": totals,
        "module_rollups": module_rollups,
        "changed_files": sorted(changed_files),
        "excluded_files": excluded_files,
        "impacted_files": sorted(impacted_files),
        "completed_work": [
            "Authentication Phase pass: backend login/logout view cleaned, MDS service-token lookup hardened, and AuthContext localStorage boot made resilient.",
            "TradeForm create/edit smoke coverage added and payload cleanup extracted into pure helpers with direct tests.",
            "MasterForm API-base resolution extracted into a pure helper with direct tests.",
            "Generic master-card rendering extracted from MasterList into a dedicated table slice with row smoke coverage.",
            "MasterForm create/edit smoke coverage added for generic master records before frontend form decomposition.",
            "License balance Excel workbook-shape regression coverage added for single and bulk exports.",
            "Large-module decomposition plan created with coverage gates and follow-up queue items.",
            "Frontend startup bundle split refined: route-wide app component preloads replaced with shell/vendor startup chunks; Excel/PDF chunks remain route-loaded.",
            "API CSRF bypass narrowed to token-authenticated requests; session-auth ledger uploads now require CSRF.",
            "Query-parameter JWT authentication restricted to GET/HEAD download/export style URLs with focused regression coverage.",
            "Ruff F841 unused-local findings reduced to 0 across the targeted Python source set.",
            "Ruff F811/E741 findings reduced from 23 to 0 across backend, scripts, mds-client, and master-data-service target set.",
            "Production-stub ambiguity removed from GE/DGFT sync paths; remote ledger fetch remains an explicit 501 contract.",
            "Ledger upload regression added for ledgers/L1.csv, ledgers/L2.csv, and ledgers/l3.csv.",
            "LicenseDetailsModel.get_item_group_data() fixed and covered by regression test.",
            "Ruff F821 undefined-name findings cleared across backend, mds-client, and master-data-service.",
            "Duplicate admin imports removed in allotment, bill_of_entry, and core admin modules.",
            "Ambiguous loop variables and unused locals cleaned in selected BOE/license exporter paths.",
            "Authorization Phase direct report endpoints now enforce ReportPermission on both router and direct /api/reports/* paths.",
            "Authorization Phase constrained Trade pass aligned trade lines and payments with TradePermission.",
            "Authorization Phase command palette and dashboard actions now hide role-protected destinations when the user lacks the matching role.",
            "Authorization Phase frozen after 46 backend/frontend authorization surfaces were verified as COMPLETED.",
            "Phase 5 frontend master display helpers extracted repeated Indian currency/number/date display formatting and removed unused MasterFormModal.",
            "Phase 5 backend golden-master scripts now use pathlib/UTF-8 JSON I/O, and ledger PDF usage no longer opens a DB connection before argument validation.",
            "Phase 5 shell-script consolidation extracted shared legacy master-sync SSH/logging/server configuration and shared MDS usage handling.",
            "Phase 5 documentation updated ADR/runbook status and replaced stale modularization plan with current audited module map.",
            "Phase 6 invoice model production hardening completed with normalization, validation, DB constraints, migrations, and 19 focused regression tests.",
            "Phase 6 license balance Excel hardening completed with bulk payload validation, duplicate worksheet formula fix, unused import cleanup, and 13 focused API regressions.",
        ],
        "pending_work": WORK_QUEUE,
        "blocked_work": [
            {
                "item": "Phase 6 invoice model Python security/dependency audit",
                "reason": ".venv/bin contains no bandit, pip-audit, safety, or semgrep executable.",
                "recommended_action": "Install or provide an approved security scanner, then run it against backend/apps/license/models/invoice.py and backend/requirements.txt.",
            },
            {
                "item": "Phase 6 license balance Excel Python security/dependency audit",
                "reason": ".venv/bin contains no bandit, pip-audit, safety, or semgrep executable.",
                "recommended_action": "Install or provide an approved security scanner, then run it against backend/apps/license/services/exporters/license_balance_excel.py and backend/requirements.txt.",
            },
            {
                "item": "Phase 6 legacy license ajax-list template full render",
                "reason": "Current URLConf does not register legacy URL names `license-list` and `license-ajax-list`; rendering `license/ajax-list.html` raises NoReverseMatch.",
                "recommended_action": "Audit the remaining legacy license templates together with their route ownership and either restore compatibility URL names or migrate the templates to current namespaced DRF/frontend routes.",
            },
        ],
        "technical_debt": {
            "ruff_full_findings": 547,
            "ruff_f811_e741_findings": 0,
            "ruff_f841_findings": 0,
            "todo_count": totals["todo"],
            "fixme_count": totals["fixme"],
        },
        "security_findings": [],
        "performance_findings": [],
        "architecture_findings": [
            "Execute coverage-gated decomposition tasks from docs/audit/large-module-decomposition-plan.md.",
        ],
        "duplicate_logic_findings": [],
        "dead_code_findings": [],
        "regression_coverage": [
            "backend/tests/test_ledger_parser.py",
            "backend/apps/license/tests/test_license_group_data.py",
            "backend/apps/license/tests/test_invoice_models.py",
            "backend/tests/test_authentication_query_param.py",
            "backend/tests/test_authorization_permissions.py",
            "backend/apps/accounts/tests.py",
            "master-data-service/masters/tests/test_api.py",
            "frontend/src/test/useAuth.test.tsx",
            "frontend/src/components/CommandPalette.test.tsx",
            "frontend/src/pages/masters/MasterForm.smoke.test.tsx",
            "frontend/src/pages/masters/masterFormHelpers.test.ts",
            "frontend/src/pages/masters/masterDisplayFormatters.test.ts",
            "backend/tests/test_export_masters_mds.py",
            "frontend/src/pages/masters/MasterList.smoke.test.tsx",
            "frontend/src/pages/TradeForm.smoke.test.tsx",
            "frontend/src/pages/tradeFormHelpers.test.ts",
        ],
        "verification_history": VERIFICATION_HISTORY,
        "audit_history": [
            {
                "timestamp": now,
                "event": "Rebuilt audit state after inventory schema repair.",
                "reason": "Prior docs/audit database included binary/vendor/generated files and marked too many files as recheck.",
            }
        ],
        "files": files,
    }


def build_graph(database: dict[str, Any]) -> dict[str, Any]:
    imports_graph = load_edge_tsv("imports.tsv")
    dependents_graph = load_edge_tsv("dependents.tsv")
    symbols = load_symbols()
    circular_edges = [
        {"a": source, "b": target}
        for source, targets in imports_graph.items()
        for target in targets
        if source in imports_graph.get(target, [])
    ]

    symbol_counts: dict[str, int] = {}
    for file_symbols in symbols.values():
        for symbol in file_symbols:
            symbol_counts[symbol["kind"]] = symbol_counts.get(symbol["kind"], 0) + 1

    return {
        "schema_version": 1,
        "generated_at": database["generated_at"],
        "source_index": database["source_index"],
        "repository": {
            "branch": database["repository_metadata"]["branch"],
            "head": database["repository_metadata"]["head"],
            "root": str(REPO_ROOT),
            "working_tree": database["repository_metadata"]["working_tree"],
            "excluded_files": database["totals"]["ignored"],
            "tracked_audit_files": database["totals"]["files"],
            "tracked_audit_lines": database["totals"]["lines"],
        },
        "hierarchy": {
            "backend_apps": sorted(
                module.removeprefix("backend/apps/")
                for module in database["module_rollups"]
                if module.startswith("backend/apps/")
            ),
            "frontend_src_areas": sorted(
                module.removeprefix("frontend/src/")
                for module in database["module_rollups"]
                if module.startswith("frontend/src/")
            ),
            "modules": database["module_rollups"],
        },
        "graphs": {
            "api_endpoint_graph": "Django urls.py and DRF routers indexed as route symbols.",
            "background_task_graph": "Celery task files indexed under backend/apps/*/tasks.py, backend/apps/reports/tasks.py, and mds-client task modules.",
            "class_dependency_graph": "Seeded from imports and symbols; detailed inheritance/composition is populated per audited module.",
            "configuration_graph": "Settings indexed under backend/config/settings, frontend config, package files, and deploy config.",
            "circular_dependency_edges": circular_edges[:100],
            "database_schema_graph": "Django models and migrations indexed; foreign-key detail is populated during backend module audits.",
            "dependent_graph_edges": sum(len(targets) for targets in dependents_graph.values()),
            "function_call_graph": "Seeded at symbol/import level; deep call graph is populated per audited module.",
            "import_graph_edges": sum(len(targets) for targets in imports_graph.values()),
            "react_component_tree": "Entry path: frontend/src/main.tsx -> App -> providers -> routes; route/component details come from .claude index and AppRoutes.",
            "react_hook_graph": "Seeded from hook symbols in .claude/index/symbols.tsv.",
            "script_graph": "Scripts indexed under scripts/**, backend/scripts/**, and root shell scripts.",
            "state_management_graph": "No Redux/Zustand found in prior architecture notes; AuthContext and ThemeContext are shared state roots.",
            "symbol_counts": symbol_counts,
            "test_graph": "Tests indexed under backend/tests, app-level tests, mds-client/tests, master-data-service tests, and frontend Vitest files.",
        },
        "impact_analysis": {
            "current_recheck_files": database["impacted_files"],
            "rule": "When a file changes, reload only the file, its imports, dependents, and mapped tests before updating this artifact.",
        },
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_dashboard(database: dict[str, Any]) -> None:
    totals = database["totals"]
    modules = database["module_rollups"]
    top_modules = sorted(modules.items(), key=lambda item: item[1]["lines"], reverse=True)[:12]
    content = [
        "# Stateful Audit Dashboard",
        "",
        f"Generated: `{database['generated_at']}`",
        "",
        "## Repository Statistics",
        "",
        f"- Files audited: `{totals['completed']}`",
        f"- Files changed directly: `{totals['changed']}`",
        f"- Files requiring dependency recheck: `{totals['requires_recheck']}`",
        f"- Files not started: `{totals['not_started']}`",
        f"- Files ignored/excluded: `{totals['ignored']}`",
        f"- Files remaining: `{totals['not_started'] + totals['changed'] + totals['requires_recheck']}`",
        f"- Total source files tracked: `{totals['files']}`",
        f"- Total source LOC tracked: `{totals['lines']}`",
        f"- Audited LOC: `{totals['audited_lines']}`",
        f"- Remaining LOC: `{totals['remaining_lines']}`",
        "- Modules completed: `0`",
        f"- Pending modules: `{len(modules)}`",
        "- Duplicate logic removed: `tracked per work item`",
        "- Dead code removed: `tracked per work item`",
        "- Imports cleaned: `duplicate admin imports removed; F821 sweep completed`",
        "- Performance improvements: `frontend startup preloads reduced; Excel/PDF generation chunks remain route-loaded`",
        "- Security improvements: `query-token JWT scope restricted; session-auth API CSRF enforcement restored; MDS service-token comparison hardened`",
        "- Tests added: `focused authentication regressions, backend regression coverage for ledger uploads, JWT query tokens, license group data, license balance Excel exports, MasterForm/MasterList/TradeForm smoke coverage, and form helper tests`",
        "- Technical debt remaining: `Ruff full baseline 547 findings; F811/E741 baseline 0 findings; F841 baseline 0 findings`",
        f"- TODO count: `{totals['todo']}`",
        f"- FIXME count: `{totals['fixme']}`",
        "- ESLint findings: `0 in latest run`",
        "- TypeScript findings: `0 in latest run`",
        "",
        "## Largest Module Rollups",
        "",
        "| Module | Files | LOC | Completed | Changed | Recheck | Not Started |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for module, stats in top_modules:
        content.append(
            f"| `{module}` | {stats['files']} | {stats['lines']} | {stats.get('completed', 0)} | {stats.get('changed', 0)} | {stats.get('requires_recheck', 0)} | {stats.get('not_started', 0)} |"
        )

    content.extend(
        [
            "",
            "## Completed Work",
            "",
            "- Authentication Phase pass: backend login/logout view cleaned, MDS service-token lookup hardened, and AuthContext localStorage boot made resilient.",
            "- TradeForm create/edit smoke coverage added and payload cleanup extracted into pure helpers with direct tests.",
            "- MasterForm API-base resolution extracted into a pure helper with direct tests.",
            "- Generic master-card rendering extracted from MasterList into a dedicated table slice with row smoke coverage.",
            "- MasterForm create/edit smoke coverage added for generic master records before frontend form decomposition.",
            "- Ledger upload regression added for `ledgers/L1.csv`, `ledgers/L2.csv`, and `ledgers/l3.csv`.",
            "- License balance Excel workbook-shape regression coverage added for single and bulk exports.",
            "- Large-module decomposition plan created with coverage gates and follow-up queue items.",
            "- Frontend startup bundle split refined: route-wide app component preloads replaced with shell/vendor startup chunks; Excel/PDF chunks remain route-loaded.",
            "- API CSRF bypass narrowed to token-authenticated requests; session-auth ledger uploads now require CSRF.",
            "- Query-parameter JWT authentication restricted to GET/HEAD download/export style URLs and covered by focused regression tests.",
            "- `LicenseDetailsModel.get_item_group_data()` fixed and covered by regression test.",
            "- Ruff F821 undefined-name findings cleared across backend, mds-client, and master-data-service.",
            "- Duplicate admin imports removed in allotment, bill_of_entry, and core admin modules.",
            "- Ambiguous loop variables and unused locals cleaned in selected BOE/license exporter paths.",
            "- Authorization Phase direct report endpoints now enforce `ReportPermission` on both router and direct `/api/reports/*` paths.",
            "- Authorization Phase constrained Trade pass aligned trade lines and payments with `TradePermission`.",
            "- Authorization Phase command palette and dashboard actions now hide role-protected destinations when the user lacks the matching role.",
            "- Authorization Phase frozen after 46 backend/frontend authorization surfaces were verified as `COMPLETED`.",
            "- Production-stub ambiguity removed from GE/DGFT sync paths; remote ledger fetch remains an explicit 501 contract.",
            "- Ruff F811/E741 findings reduced from 23 to 0 across the targeted Python source set.",
            "- Ruff F841 unused-local findings reduced to 0 across the targeted Python source set.",
            "- Phase 7 Reporting & Exports started with the allotment PDF coordinate-grid helper hardened and covered by direct CLI tests.",
            "",
            "## Verification History",
            "",
        ]
    )
    content.extend(f"- {item}" for item in database["verification_history"])
    content.extend(
        [
            "",
            "## Blocked Work",
            "",
            "- None currently blocked.",
            "",
            "## Skipped Work",
            "",
            "- Generated/cache/vendor/binary outputs are recorded as `IGNORED` in `audit-database.json` under `excluded_files`.",
            "",
            "## High Risk Changes",
            "",
            "- Any changes to `backend/apps/license/models/__init__.py`, `backend/apps/core/models/__init__.py`, `frontend/src/shared/api/client.ts`, or shared UI primitives require blast-radius checks from `.claude/index/dependents.tsv`.",
        ]
    )
    (AUDIT_ROOT / "dashboard.md").write_text("\n".join(content) + "\n", encoding="utf-8")


def write_work_queue() -> None:
    lines = [
        "# Stateful Work Queue",
        "",
        "Work is processed in priority order. Completed tasks are removed or marked `DONE`; changed files are requeued as `REQUIRES_RECHECK` in `audit-database.json`.",
        "",
        "| ID | Priority | Stream | Status | Work | Verification |",
        "|---|---:|---|---|---|---|",
    ]
    for item in WORK_QUEUE:
        lines.append(
            f"| `{item['id']}` | {item['priority']} | {item['stream']} | {item['status']} | {item['title']} | {item['verification']} |"
        )
    lines.extend(
        [
            "",
            "## Module Pipeline",
            "",
            "1. Authentication",
            "2. Authorization",
            "3. Users",
            "4. Roles & Permissions",
            "5. Master Data",
            "6. License",
            "7. Allotments",
            "8. Bills of Entry",
            "9. Inventory",
            "10. Reports",
            "11. Documents",
            "12. Uploads",
            "13. Background Tasks",
            "14. Shared Services",
            "15. Utilities",
            "16. Scripts",
            "17. Frontend Shared Components",
            "18. Frontend Hooks",
            "19. Frontend Pages",
            "20. Trade",
        ]
    )
    (AUDIT_ROOT / "work-queue.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_readme() -> None:
    content = """# Codex Stateful Audit

This directory contains the persistent state for the repository-wide audit.

- `build_audit_state.py` rebuilds the audit layer from the current repository state and the existing `.claude/index` graph.
- `repository-knowledge-graph.json` records graph summaries and impact-analysis rules.
- `audit-database.json` records every tracked file with checksum, audit status, metrics, and quality scores.
- `work-queue.md` records prioritized engineering work.
- `dashboard.md` records the live progress dashboard.

Workflow:

1. Use `.claude/index` to find symbols and blast radius.
2. Audit only files marked `NOT_STARTED` or `REQUIRES_RECHECK`.
3. After an edit, re-run this generator and affected tests/lint/type checks.
4. Do not mark a file `COMPLETED` unless its relevant verification has passed.
"""
    (AUDIT_ROOT / "README.md").write_text(content, encoding="utf-8")


def main() -> None:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    database = build_database()
    graph = build_graph(database)
    write_json(AUDIT_ROOT / "audit-database.json", database)
    write_json(AUDIT_ROOT / "repository-knowledge-graph.json", graph)
    write_dashboard(database)
    write_work_queue()
    write_readme()


if __name__ == "__main__":
    main()
