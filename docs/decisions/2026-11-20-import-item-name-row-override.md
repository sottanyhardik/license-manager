# Licence Detail → Import Items: per-row Item Name correction = row override (2026-11-20)

Status: owner decision (2026-11-20), implementation in progress on `feature/v5` (uncommitted).

## Context
Licence import items get their Item Names (`LicenseImportItemsModel.items` → `core.ItemNameModel`) mostly from saved
description mappings (`ImportDescriptionMapping`, REPLACE semantics, 17,078 APPLIED records locally). Those mappings are
re-applied automatically: `auto_apply` (new / re-described import item) and `apply_for_licence` (every licence save). A
plain per-row edit would therefore be silently reverted by the next licence save.

## Decision (owner)
1. A correction made in Licence Detail → Import Items is a **row override**: it applies to that one import item only.
   Description mappings (row save, bulk, reapply, auto apply, licence save) skip overridden records and report them as
   `overridden`; Product Matching approvals refuse them. "Revert to description mapping" removes the override and
   re-applies the description mapping (versioned).
2. **One Item Name per row.** A row with several links shows as Multiple (ambiguous); saving replaces them with one, the
   previous links are audited. Clearing leaves the row deliberately Not Mapped (still protected).
3. Writes: LICENSE_MANAGER (same as the Mapping workspace). Reads: the licence viewset's read permission.

## Implementation shape
- New table `ImportItemNameOverride` (OneToOne import item; `item_ids`, `previous_item_ids`, reason, user, timestamps) — a
  protection flag + audit snapshot; the M2M stays the source of truth. A status on `ImportItemDescriptionMapping` was not
  used because its `mapping` FK is required, so rows without a description mapping could not be protected.
  Additive migration, no data change. New `MappingChange` kind `IMPORT_ITEM_OVERRIDE`.
- Every save: one `MappingChange` (plan archive) before links are written, one `ProductIntelAuditEvent`, licence marked
  for re-plan (owner decision: mapping changes auto-replan). Concurrency: `expected_item_ids` per row (409 on mismatch).
- SION / HSN: existing `description_mapping._conflict` — blocking conflicts refuse the save; "Not verified" notes are
  stored and shown (owner HSN/SION policy).
- Classification only: no quantity, CIF, debit or balance write; canonical CIF rules untouched.

## Amendment (owner, 2026-11-20, later) — global Description + HSN approval

A Licence Detail Item Name selection or removal is a **global approved decision** for every import item (all licences)
with the same strict description key (`description_mapping.description_key`: whitespace / case / punctuation spacing only;
original text stored) **and** the same HSN code (trimmed; "no HSN" is its own value; a blank description is never
globally mappable). Statuses: `USER_APPROVED` (Item Name) and `USER_APPROVED_CLEAR` (deliberately no Item Name).

Precedence, highest first: **row override** (kept as a one-record exception) → **Description + HSN approval** → saved
description-only mapping (`ImportDescriptionMapping`, unchanged for every other combination; no data migration) →
automatic writers (rule auto-link even if `RULE_AUTO_LINK` is re-enabled, consolidation, management commands, imports,
background tasks), which never override an explicit decision. Item master consolidation re-points an approval to the
surviving Item Name with an audited version (never silent); a cleared combination never gains links automatically.
Approved / cleared combinations are excluded from pending Product Mapping work and listed separately (records, licences,
revise, revoke). Migration `0067` (new tables only); not applied without owner approval.
