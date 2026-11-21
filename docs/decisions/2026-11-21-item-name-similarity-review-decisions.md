# 2026-11-21 — Item Name similarity review: owner decisions (NOT yet executed)

Read-only scan of `core.ItemNameModel` on local `lmanagement` (inside a `READ ONLY` transaction): 110 item names
(102 active), 5,995 pairs compared (all pairs), 15 candidate groups (0 exact, 0 very high, 2 high, 13 possible).
Machine-readable record: `data/2026-11-21-item-name-merge-decisions.json`.

Every group was reviewed one at a time. Each MERGE was confirmed separately after the user saw its preview.

## APPROVED merges (6) — all move 0 references, financial delta 0

| Group | Canonical (survives) | Sources (inactive + point to canonical, never deleted) | Note |
|---|---|---|---|
| ING-283-286 (+ covers 186↔283, 186↔286) | 186 PAPER BOARD | 283 PAPER BOARD - E1, 286 PAPER BOARD - E5 | 186 already has E1/E5 |
| ING-282-285 | 271 PAPER | 282 PAPER - E1, 285 PAPER - E5 | 271 already has E1/E5 |
| ING-191-271 | 271 PAPER | 191 PAPER & PAPER | **Norm union approved:** 271 gains E126, E132, A3627 |
| ING-281-287 | 94 PP | 281 PP - E5, 287 PP - E1 | 94 has all 5 norms |
| ING-216-279 | 216 ALUMINIUM FOIL | 279 Aluminium Foil - E132 | 216 has E132 |
| ING-267-274 | 267 NUT & NUTS | 274 NUT & NUTS - E132 | 267 has E132 |

## KEEP SEPARATE (7)
127/130 Hot vs Cold Rolled Steel · 171/224 Fruit/Cocoa vs Fruit Cocktail · 206/211 HDPE vs LDPE ·
105/106 Rear vs Front wheel tyre · 103/104 Brake vs Seat assembly · 108/109 Rear vs Front wheelrim ·
145/175 Food Colour vs Food Flavour. Future scans should not raise these pairs again unless a name changes.

## Executed 2026-11-21 (local dev DB `localhost/lmanagement`)
All 6 approved merges ran through `manage.py item_name_merge execute <group> --confirm`, one group at a time.
Result per group: 0 leftover references, 0 duplicate M2M rows, financial difference 0. Licences checked:
455 / 167 / 167 / 844 / 458 / 313. Total item names are still 110; 9 sources are inactive and kept, with 9 current
`ItemNameMergeSource` alias rows and 12 audit rows. Item 271 norms are now E1, E5, E126, E132, A3627.
Rollback: `item_name_merge rollback <group> --confirm` (tested; refuses if a record changed since the merge).

Engine limits (independent review 2026-11-21): merges that move live references are refused by default. Raw
through-row updates bypass the replan / cache receivers, and the snapshot does not yet measure item-level pivot
splits. `ItemNameModel.norms` is not in the master-sync payload, so 271's new norms are local to this server.
The sources' `is_active=False` does go out through master sync.

## Execution constraints
- Run these only through the audited merge engine (`merged_into` pointer, audit rows, pre/post financial snapshot,
  rollback), which has not been built yet. Do **not** use `merge_item_name_duplicates --apply` or
  `merge_norm_suffixed_item_names --apply`: they pick the lowest ID as survivor and physically delete rows.
- Before executing, re-run the reference counts. If any source now has references, show a new preview and get
  fresh confirmation.
- Prerequisite: local DB has `license/0067_import_item_mapping_approval` unapplied (needs `migrate` approval).
