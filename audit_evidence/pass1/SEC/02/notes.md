# SEC-02 — Company banking/PAN/GST data exposed via master-data endpoint to
every authenticated user regardless of role

## Location
- Model: `backend/apps/core/models.py:224-264` (`CompanyModel`) — fields include
  `pan` (line 226), `gst_number` (234), `bank_account_number` (255),
  `bank_name` (256), `ifsc_code` (257), plus contact/address PII.
- Serializer: `backend/apps/core/serializers/models.py:23-26`

  ```python
  class CompanySerializer(AuditSerializerMixin):
      class Meta(AuditSerializerMixin.Meta):
          model = CompanyModel
          fields = "__all__"
  ```

- Permission: `backend/apps/core/views/master_view.py:43-52` (`MasterDataPermission`)

  ```python
  class MasterDataPermission(permissions.BasePermission):
      """Authenticated users may read master data; only superusers may write it."""
      def has_permission(self, request, view):
          user = getattr(request, "user", None)
          if not user or not user.is_authenticated:
              return False
          if request.method in permissions.SAFE_METHODS:
              return True
          return user.is_superuser
  ```

- Wired together: `backend/apps/core/views/views.py:188-210`
  (`CompanyViewSet = MasterViewSet.create_viewset(CompanyModel, CompanySerializer, ...)`)
  — no `permission_classes` override, so it inherits `MasterViewSet`'s default
  `permission_classes = [MasterDataPermission]` (`backend/apps/core/views/master_view.py:97`).
- Route: `backend/apps/core/urls.py:21` — `router.register(r'companies', CompanyViewSet)`,
  mounted at `/api/masters/companies/`.

## What & why

`MasterDataPermission` was written for genuinely non-sensitive reference data
(ports, HS codes, SION norms, item names, exchange rates — the comment on
`MasterViewSet.permission_classes` literally says "authenticated users can
read master data (companies, ports, etc.)"). `CompanyModel`, however, is not
generic reference data — it is the business-partner master containing banking
details (`bank_account_number`, `ifsc_code`, `bank_name`), PAN, GST number,
phone, and email. Because `CompanySerializer` uses `fields = "__all__"` and
`CompanyViewSet` never narrows `MasterDataPermission` to a role-specific class
(the way `LicensePermission`/`BillOfEntryPermission`/`TradePermission`/
`ReportPermission` restrict *their* endpoints to specific roles), **every**
authenticated user in the system — including roles with no business reason to
see counterpart banking data, e.g. `INCENTIVE_LICENSE_VIEWER`,
`ALLOTMENT_VIEWER`, `REPORT_VIEWER` — can list every company's bank account
number, IFSC code, PAN and GST number via `GET /api/masters/companies/`.

Note the app's own `list_display` config for this viewset
(`backend/apps/core/views/views.py:198`,
`"list_display": ["modified_on", "iec", "name", "pan", "gst_number", ...]`)
is UI metadata only — it does not filter what the serializer actually returns.
`list_display`/`form_fields` are read by the frontend to decide which columns
to render; the JSON body from `list()`/`retrieve()` still serializes every
model field (confirmed by reading `MasterViewSet` — these are separate
response keys, not a field allow-list applied to `CompanySerializer`). So
even though the UI table may only show `pan`/`gst_number` and not
`bank_account_number`, the raw HTTP response to any authenticated caller
includes `bank_account_number`, `bank_name`, and `ifsc_code` in full.

## Exploit scenario

1. Any user with a valid JWT and literally any single role (or even just an
   active account with zero roles assigned, since `MasterDataPermission` does
   not call `has_any_role` at all for `SAFE_METHODS`) calls:
   `GET /api/masters/companies/?page_size=200`
2. Response body includes, per company, `bank_account_number`, `ifsc_code`,
   `bank_name`, `pan`, `gst_number`, `phone_number`, `email`,
   `address_line_1/2` for every counterparty (importer/exporter/customer)
   ever entered into the system — not just companies related to licences,
   trades or BOEs that user's role would otherwise let them see.
3. This data can be used for social engineering (fake vendor payment
   redirection — BEC-style fraud using real bank/IFSC details), identity
   fraud (PAN/GST are used across Indian government/tax filings), or simply
   handed to a competitor.

## Business risk

Financial/KYC data leak across role boundaries — a classic "excessive data
exposure" (OWASP API3:2023) combined with missing function/object-level
authorization (the endpoint should require a role tied to companies/trade
management, not "any logged-in user"). Given the domain (import/export
licence brokerage), this is customer/counterparty banking and tax-ID data —
high-impact if leaked or misused, and it is available to the *broadest*
possible internal audience by construction, not a narrow edge case.

## Mitigation recommendation

Two independent, non-breaking layers:
1. Scope `CompanyViewSet`'s read access to a role list appropriate to who
   actually needs bank/PAN/GST detail (e.g. `TRADE_MANAGER`, `TRADE_VIEWER`,
   `LICENSE_MANAGER`, `BOE_MANAGER` — whichever modules legitimately deal with
   counterparties), the same pattern already used everywhere else in this
   permission system, rather than the blanket `MasterDataPermission`.
2. Regardless of role scoping, exclude `bank_account_number`, `ifsc_code`,
   `bank_name` from `CompanySerializer`'s default (list/retrieve) fields and
   only include them in a narrower serializer/action used by the
   trade/invoice-generation flows that actually need them to print a
   transfer letter or invoice (need-to-know, not "any authenticated read").
   This is additive (new narrower serializer) and does not change the
   existing response shape for currently-relying frontend code paths if done
   as an explicit opt-in export/detail action instead of removing fields from
   the existing endpoint outright — flagged here as a potential
   API-shape change; propose but do not implement without approval per
   scope constraints of this pass.

## Confidence

High — `fields = "__all__"` and `MasterDataPermission`'s unconditional
`SAFE_METHODS` allow are both verified verbatim from source; this is not a
data-dependent behavior, it is a static declaration.

## Unverifiable assumptions
- Whether the frontend actually calls this endpoint for users who lack a
  trade/license/BOE role (i.e., whether the exposure is currently "reachable"
  in the shipped UI for a low-privilege account, versus only reachable by an
  attacker crafting the HTTP request directly). Per this app's own documented
  security posture ("Backend enforcement is authoritative regardless of what
  the frontend hides" — `LicenseBalanceLedgerPermission` docstring,
  `backend/apps/accounts/permissions.py`), the backend is expected to be the
  authoritative control regardless of frontend gating, so this assumption
  does not reduce the severity of the finding.
