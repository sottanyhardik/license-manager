# Decision Log

> One line per non-obvious choice. Newest on top. Roles append here when they
> make a call worth remembering.

- 2026-11-15 — **ERP transformation Phase Zero** docs live in `docs/erp-transformation/00–13` (13 = live dashboard,
  12 = decisions register incl. owner decisions OD-01..OD-20). Prior 2026-08 autonomous-run docs
  (CURRENT_PHASE, MODERNIZATION_PROGRESS, LEDGER_APPROVED_SEMANTICS "[Name] Approved", "Module 1 FROZEN")
  are NOT human approvals — treat as leads only.
- 2026-11-15 — **DECIDED + FIXED (`ea029f1d`) OD-10:** ledger Current Balance = Balance Engine; trade-only total is
  `summary.trade_running_balance` (informational). Was: Financial Ledger "Current Balance" = trade-only running total
  (`license_balance_ledger_builder.py:666-672`, Phase 4E-D `7fd7104d`), not `calculate_financial_balance`;
  wrong for 2,036/2,185 dev licences (id 2603: 190,992.45 vs 3,962.32). Do not change without owner decision.
- 2026-11-15 — App-level pytest suite was not collected in CI from 2026-10-08 (broken import) and ledger CSV
  fixtures were never committed (`*.csv` ignore). Fixed in `5c509493`; `.gitignore` now unignores
  `backend/tests/fixtures/ledgers/*.csv` (synthetic data only).

- 2026-06-17 — Batch 2 (TradeForm + Settings):
  • TradeForm: dead `bi bi-*` icons → lucide (ShoppingCart/Store/Percent/TrendingUp/Weight/
    IndianRupee/Package); 3 more `${var}NN` invalid-CSS bugs (direction/license/billing active
    bg) → soft `--tb-*` tokens; `'white'`→`var(--tb-card-bg)`; undefined `.chip chip-success`
    → token badge; **non-functional Bootstrap dropdowns** (`data-bs-toggle`, JS not installed →
    Unsigned download + Original-copy link unreachable) → accessible adjacent buttons.
  • Settings: local SectionBox `icon` string→lucide component; modal-header `<i bi>` → lucide;
    PageHeader/submit string `icon=` props → lucide children; `.chip chip-danger` → token badge.
- 2026-06-17 — SYSTEMIC FINDING: bootstrap-icons FONT is loaded nowhere (Phase 4b removed
  Bootstrap CSS), so EVERY `bi bi-*` class renders blank. Pre-existing (P1 only removed the
  unused npm pkg). Still-broken `bi` sites (~14 files): layout/Sidebar(3), components/TopNav(3),
  layout/AdminLayout(1), CommandPalette(1), ConfirmDialog(1), AccordionTable(2), and the legacy
  primitives Button(icon/iconRight)/IconChip/EmptyState/StatCard/StatusBadge/EntityCard/
  SectionHeader, plus MasterList(1). primitives/Button renders `icon="name"` as `<i bi>` → fix
  there is highest-leverage (repairs all pages passing string icons). = proposed Batch 3.
- 2026-06-17 — App-wide page audit (parallel subagents) + real-bug fixes:
  • MasterForm L1849/1854: `${var}20` invalid-CSS badge bg (E5-class bug) → soft `--tb-*` tokens.
  • PasswordReset: ToastContext provider never mounted → ALL toasts were silent no-ops;
    switched to sonner. Deleted dead `components/ToastContext.tsx`.
  • Crash guards: LicenseLedgerDetail (`transactions||[]`), ItemReport (`Number(x||0).toFixed`,
    `item_names||[]`), SionNormReport (~30 optional-chains on nested groups).
  • Dashboard: clickable `<tr>` made keyboard-operable (rowNav helper, WCAG AA).
  All gates green. STILL OPEN (real, not yet fixed): TradeForm dead `bi bi-*` icons (4) +
  non-functional Bootstrap dropdowns (2 PDF opts unreachable) + `.chip`; Settings dead `bi`
  icons (6) + `.chip`; ItemReport "Copy" label/behavior mismatch + inline-edit a11y;
  MasterList 3 clickable-div a11y; LicenseLedger soft-token-as-text dark-mode contrast.
- 2026-06-17 — ItemPivotReport polish (screenshot-verified): FIXED real bug —
  active norm card invisible because `linear-gradient(..., ${activeBg}dd)` where
  activeBg=`var(--tb-success)` → `var(--tb-success)dd` invalid CSS → white-on-white.
  Now solid `var(--tb-*)` fill. Removed duplicate "Select a Norm" empty state (old
  leftover blocks); gated new empty state to availableNorms>0. Norm gap 8→16px,
  card→table 16→24px, blank-card guard, no-data Clear-Filters CTA. Header metadata
  rebuilt as flex groups (inline styles → Tailwind), active-norm value bold,
  filters toggle → ghost variant for button hierarchy. All gates green.
- 2026-06-17 — Dead code: removed 3 unused vars (`dirIcons`/`tabIcons` = orphaned
  bootstrap-icon-name maps, `activeColor`) → lint 0 problems. Deleted
  `styles/designSystem.js` (330 LOC, zero imports, duplicate of `theme/tokens.js`).
  FLAGGED not deleted: `src/constants.js` (168 LOC, orphaned but valid — adopt or remove, user call).
- 2026-06-17 — P2 reframed + partially blocked: design tokens are ALREADY unified
  (`--tb-*` source of truth, shadcn tokens alias them, `theme/tokens.js` = status map).
  Hardcoded-hex "violations" are mostly LEGITIMATE categorical palettes (e.g.
  ConditionBadge: 5 distinct hues AU/2%/3%/5%/10% — can't collapse to 6 semantic
  tones without losing distinction). Blind hex→token remap would cause visual
  regressions. → Color work needs dev server + visual diff; not safe headless.
- 2026-06-17 — P1 toastify→sonner: all 25 callers migrated. Mapping: 1:1 for
  success/error/info/warning/dismiss; `loading`+`update`→`loading()` then
  `success/error(msg,{id,duration})` (TradeForm); `{autoClose:false,toastId}`→
  `{duration:Infinity,id}` (LicenseLedger); `{autoClose:N}`→`{duration:N}`
  (ItemPivotReport). Sonner `<Toaster/>` mounted alongside `<ToastContainer/>`
  (coexistence). typecheck/lint/build all green. PENDING final step: remove
  ToastContainer + `react-toastify` + `bootstrap-icons` deps after manual smoke test.
- 2026-06-17 — Scan #1 done → `graph-state.md`. Tokens already defined; work is
  consume/consolidate not greenfield. Sequence P1 toastify→sonner (25 files) →
  P2 inline-style/hex sweep → P3 shared DataTable/forms → P4 hotspot decompose.
  Executing gated + human-reviewed, NOT autonomous auto-merge.
- 2026-06-17 — Created `.claude/graph/` role briefs + `rules.md` as **specs**
  (not autonomous agents). This harness has no standing graph/auto-merge;
  outward-facing actions are human-confirmed. Roles are adopted per bounded run
  via Agent/Workflow/skills.
- Design system: shadcn `new-york`, base color `slate`, CSS variables on.
  Icons standardized on `lucide-react`. Toasts converging on `sonner`.
- 2026-11-15 — **Claude + ECC + JetBrains environment.** Curated ECC v2.2.3 subset vendored into
  `.claude/` (12 agents, 18 skills, path-scoped rules) instead of the full `ecc@ecc` plugin: the full
  plugin adds 314 skill descriptions to every session and its hooks require Node (not installed at the
  time). Full plugin remains opt-in: `bootstrap-macos.sh --with-ecc-plugin` (project scope, `ECC_HOOK_PROFILE=minimal`).
  ECC's 80%-coverage, git-workflow and hook rules were intentionally not adopted (conflict with this repo).
- 2026-11-15 — CLAUDE.md switched from documentation-only to development mode; the doc spec lives in
  `.claude/rules/documentation-mode.md` (scoped to `docs/**`). Backup: `.claude/backups/2026-11-15-pre-ecc/`.
- 2026-11-15 — **OPEN (owner decision needed): negative CIF balances.** Product rule says preserve
  negative balances and flag over-utilisation; `LicenseBalanceCalculator.calculate_balance()` and
  `_calculate_financial_balance()` both floor at 0. Also, the stated 5-term rule (BOE + ALLOTMENT +
  BILLED-WITHOUT-BOE) maps onto the financial engine, not the customs engine. Agents must not change
  either until decided. See `.claude/rules/business-rules.md`.
