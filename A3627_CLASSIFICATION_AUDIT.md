# A3627 Classification Audit

Read-only audit of the local database (`lmanagement`, PostgreSQL). No production data was modified.

## 1. Scope and data

- A3627 export rows: 220 licences.
- A3627 import lines (distinct): **1,200**.
- Source of "Sr. No.": `LicenseImportItemsModel.serial_number`, the line number inside each licence.

## 2. Serial numbers are not a stable key

The same Sr. No. carries different products across licences. The classifier therefore decides on description and HSN, and treats serial only as a diagnostic.

| Serial | Lines | Products found under this serial (registry result) |
|---|---:|---|
| 1 | 219 | RUTILE (glass formers), 1 Titanium Dioxide |
| 2 | 84 | Aluminium Oxide |
| 3 | 80 | Soda Ash, 1 Borax, 5 unmatched "Modifiers (Potash)" |
| 4 | 83 | Titanium Dioxide, 1 unmatched Phosphoric Acid |
| 5 | 83 | PP |
| 6 | 133 Al oxide + 83 wooden | **Aluminium Oxide and Wooden Pallets under the same serial** |
| 11 | 134 | Soda Ash |
| 17 | 134 | Titanium Dioxide |
| 22 | 133 | PP (and 104 lines naming BB-Board, PP Laminated Board, Kraft Liner, Wooden) |

Conclusion: a serial gate would mislabel real records (serial 6 carries both oxide and wooden lines). Serial is accepted by the API and returned in diagnostics, but it never changes a category.

## 3. Sr. No. 1 — RUTILE

Real Sr. No. 1 lines are "Glass Formers namely" lists (Silica other than Fumed Silica, Borax, Phosphoric Acid, Arsenic Trioxide, Rutile). They use HSN `32061190`, `32061110` or `28110000`, with many spelling variants: `GLASS FORMERS NAMEY`, `BORIX`, `BOARX`, `HSN 28100020` for boric acid.

- The existing matcher excluded any description containing "other than". That removes the approved "Silica (other than Fumed Silica)" wording: 158 of the 167 glass-former lines contain "other than", and none contain "other than rutile". Fixed in the registry: only "other than **rutile**" blocks RUTILE.
- HSN `32061110` is also used by Sr. No. 17 Titanium Dioxide. HSN alone is therefore AMBIGUOUS, not RUTILE.

## 4. Sr. No. 6 — Aluminium Oxide

Real lines: "Intermediates namely (a) Aluminium Oxide 28182000 (b) Zinc Oxide 28170010 (c) Zirconium Oxide 28256010". HSN variants: `28170000` for Zinc Oxide. Two lines also list **(C) RUTILE** in the same oxide list. These are AMBIGUOUS and not classified (see §8).

## 5. Sr. No. 11 — Soda Ash

Real lines: "Modifiers namely (a) Magnesium Oxide 25199040 (b) Soda Ash 28362010 (c) Sodium Nitrate 28342990 (d) Potash 28152000 (e) Potassium Nitrate 28342100". Standalone "Modifiers (Potash)" lines carry HSN `28200000` (5 lines, serial 3), a conflicting HSN. Standalone "Potash" `28364000`, "Sodium Nitrate" `31025000`, "Potassium Nitrate" `28000000`, "Magnesium Oxide" `28200000` are also HSN variants. They are unmatched and reported in §8.

## 6. Sr. No. 17 — Titanium Dioxide

Real lines: "Other Special Additives namely: (a) Clay 25080000 (b) Selenium 28049000 (c) Nucleating Agents (Titanium Dioxide other than Rutile Grade) 32061110 (d) Barium Carbonate 28366000". Spelling variants: "Rutile Garde", "other than 17 Rutile Grade", "TITRANIUM DIOXIDE". This is the mandatory negative case: "other than rutile" must never be RUTILE.

## 7. Sr. No. 22 — Packing and board

- Most lines are "PACKING MATERIAL / PP" with HSN `39021000`.
- 104 lines are composites that name several products with their own HSN: `48070030` BB-Board 2/S Glazed 900 gsm, `48115900` PP Laminated Board 380–580 gsm roll, `48041100` Kraft Liner 135–160 gsm roll, plus wooden sheets / pallets (HSN `44150000`/`44152000`).
- Composites are multi-product. Their value is one number on the line, so there is no per-product value to split. They are classified by the declared line HSN and flagged `multi_product` (127 lines). Splitting them needs a business decision (§8).
- Reference values from the brief: Kraft Liner `1,50,008.47` and Wooden `1,03,121.00`. Each appears once as text in a description. Neither matches a field value, so they were not used for classification.

## 9. Existing and duplicate rules

| Location | Rule | Status |
|---|---|---|
| `services/a3627_classifier.py` | Registry (new). Single A3627 source for the pivot. | Authoritative |
| `services/product_classification.py` | Delegates A3627 to the registry. Previously had its own RUTILE/BORAX/SILICA/TiO2 logic. | Duplicate removed |
| `utils/item_matcher.py` (`get_item_filters`) | Django Q filters for A3627 linking (RUTILE, TITANIUM, SILICA, BORAX, SODA ASH, PP, ALUMINIUM FOIL). | **Second implementation, still active.** Kept in parity by tests on the sample set only. |
| `services/sion_legacy_configurations.py` | A3627 legacy planner expressions, `is_active: False`. | Inactive. Not used at runtime for classification. |
| DB `SionPlanningRule` rows | Not checked for A3627 in production. | Not verified |

## 10. Storage

No model stores a product category. The classification is computed on demand by the pivot service and by the matcher. Therefore **no database backfill is needed for the pivot**. Only the matcher writes links (`ItemNameModel` associations) and those are not changed by this work.

## 8. Records requiring business review

Counts from the final run (1,200 lines): CONFIRMED 1,180, UNMATCHED 18, AMBIGUOUS 2. Licence numbers as stored.

**AMBIGUOUS (2)** — Sr. 6 oxide list that also names RUTILE: licences `0310506768` and `0310545763`, serial 6, HSN 28182000, "INTERMEDIATES NAMELY (A) ALUMINIUM OXIDE (B) ZINC OXIDE (C) RUTILE (D) ZIRCONIUM OXIDE". Decision needed: Aluminium Oxide, or RUTILE, or split.

**UNMATCHED (18)**
- `0310506768`: Phosphoric Acid HSN 28092000 (serial 4); Arsenic Trioxide HSN 28112900 (serial 5); Magnesium Oxide HSN 28200000 (serial 12); Sodium Nitrate HSN 31025000 (serial 14); Potash HSN 28364000 (serial 15); Potassium Nitrate HSN 28000000 (serial 16); Barium Carbonate HSN 25112000 (serial 21). Each is a listed item under a different HSN from the brief. Decision needed: accept the HSN variant, or leave unclassified.
- `0310739040`, `0310736683`, `0310739039`, `0310736682`, `0310739038`: "MODIFIERS NAMELY (A) POTASH" with HSN 28200000 (serial 3), no Soda Ash. Decision needed: Soda Ash, or leave.
- `0310610591`: 6 blank lines (no HSN, no description). Cannot be classified; needs data correction.

**Multi-product composites (127 lines, CONFIRMED but flagged)** — Sr. 22 lines whose declared HSN is 39021000 but whose description names BB-Board, PP Laminated Board, Kraft Liner or wooden pallets. Decision needed: whether the value on the line should be split by product.

**Quantity constraint (not implemented)** — Borax "not exceeding 10%" of export product (Sr. 1 text). This is an aggregate rule across lines and was not enforced.
