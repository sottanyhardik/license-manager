# A3627 Classification Rules

Authoritative file: `backend/apps/license/services/a3627_classifier.py` (`classify_a3627`).
The item pivot calls it through `product_classification.classify_product` for norm `A3627`.

Serial number is accepted and returned for diagnostics. It never changes the category.

## Evaluation order (first match wins)

| # | Rule id | Category | Condition | Status if matched |
|---|---|---|---|---|
| 1 | `A3627.SR17.TITANIUM_DIOXIDE` | TITANIUM DIOXIDE | (description has titanium dioxide, incl. "TITRANIUM" typo, AND "other than") OR (HSN 3206 AND "other than rutile") | CONFIRMED |
| 2 | `A3627.SR17.TITANIUM_DIOXIDE_COMPOSITE` | TITANIUM DIOXIDE | ("other special additives" or "nucleating agents") AND (titanium dioxide OR HSN 32061110) | CONFIRMED |
| 3 | `A3627.SR01.RUTILE_GLASS_FORMERS` | RUTILE | Not "other than rutile", not "soda ash", "glass former" present, AND (HSN 32061190/32061110/28110000 OR "rutile" in description) | CONFIRMED |
| 4 | `A3627.SR01.RUTILE_HSN_3206` | RUTILE | Not "other than rutile", not "soda ash", HSN 3206* AND "rutile" in description | CONFIRMED |
| 5 | `A3627.SR01.RUTILE_HSN_ONLY` | none | HSN 32061190/32061110 with no glass former, rutile, TiO2 or composite wording | **AMBIGUOUS** (not classified) |
| 6 | `A3627.SR06.ALUMINIUM_OXIDE` | ALUMINIUM OXIDE | Description names aluminium oxide, aluminum oxide, zinc oxide or zirconium oxide. If the same line also says RUTILE: AMBIGUOUS | CONFIRMED / AMBIGUOUS |
| 7 | `A3627.SR06.ALUMINIUM_OXIDE_HSN_ONLY` | none | HSN 28182000/28170010/28256010 with no description | **AMBIGUOUS** |
| 8 | `A3627.SR11.SODA_ASH` | SODA ASH | HSN 28362010, OR "soda ash" in description, OR ("modifiers namely" and "soda") | CONFIRMED |
| 9 | `A3627.ALUMINIUM_FOIL_7607` | ALUMINIUM FOIL | HSN 7607* or "7607" in description (never PP) | CONFIRMED |
| 10 | `A3627.GLASS_FORMER.SILICA` | SILICA | HSN 28110000, "silica" in description, and either no "fumed silica" or "other than fumed silica" present | CONFIRMED |
| 11 | `A3627.GLASS_FORMER.BORAX` | BORAX | HSN 28401900 OR "borax" in description | CONFIRMED |
| 12 | `A3627.SR22.HSN.*` | PP / BB-BOARD / PP LAMINATED BOARD / KRAFT LINER / WOODEN SHEETS / PALLETS | Declared HSN: 39021000→PP, 48070030→BB-BOARD, 48115900→PP LAMINATED BOARD, 48041100→KRAFT LINER, 4415*→WOODEN SHEETS / PALLETS. Flagged `multi_product` if the description names more than one product | CONFIRMED |
| 13 | `A3627.SR22.DESC.*` | Same products | Description fallback (first match): PP laminated, BB board, kraft liner, wooden / pallet, then PP (whole word, never chapter 48) | CONFIRMED |
| – | `A3627.UNMATCHED` | none | No rule matched | UNMATCHED (generic E5 rules then apply in the pivot) |

## Precedence and exclusions

- "other than **rutile**" is never RUTILE (Sr. 17 mandatory exclusion). A generic "other than" does not exclude; "Silica (other than Fumed Silica)" is the approved glass former.
- "soda ash" anywhere excludes RUTILE, matching the legacy matcher.
- Sr. 6 oxide list that also names RUTILE is AMBIGUOUS, not ALUMINIUM OXIDE and not RUTILE.
- HSN 32061110 alone is AMBIGUOUS. It is used by Sr. 17 TITANIUM DIOXIDE and by Sr. 1 rutile.
- Sr. 22 composite lines keep the declared HSN category and are flagged. Their values are not split.
- Chapter 48 (paper and board) is never PP by description. Those lines fall through to the generic rules (PAPER).

## Normalization

- HSN: digits only, leading zeroes kept (`3206.11.10` → `32061110`).
- Description: lower case, punctuation and hyphens become spaces, whitespace collapsed (`BB-BOARD` = `bb board`).
- Spelling tolerated: `TITRANIUM DIOXIDE`, `GLASS FORMERS NAMEY`, `BORIX`, `BOARX`.

## Labels

All labels are uppercase canonical identifiers, defined once as constants in `a3627_classifier.py`: `RUTILE`, `ALUMINIUM OXIDE`, `SODA ASH`, `TITANIUM DIOXIDE`, `PP`, `BB-BOARD`, `PP LAMINATED BOARD`, `KRAFT LINER`, `WOODEN SHEETS / PALLETS`, `ALUMINIUM FOIL`, `SILICA`, `BORAX`.

## Cache

The item pivot JSON cache key includes `registry_version()`, a hash of `a3627_classifier.py` and `product_classification.py`. Any rule or label change misses the cache at once.

## Known gaps (not classified, reported)

See `A3627_CLASSIFICATION_AUDIT.md` §8 and the release report: standalone Phosphoric Acid, Arsenic Trioxide, Magnesium Oxide, Potash, Sodium Nitrate, Potassium Nitrate, Barium Carbonate under HSN variants; blank rows; Sr. 6 RUTILE conflicts.
