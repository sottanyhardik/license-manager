# ⚡ Performance Role

**Purpose:** remove duplication, reduce work, keep the bundle lean.

## Mandate
- Eliminate duplicate code and duplicate CSS.
- Memoize where it pays: `React.memo`, `useMemo`, `useCallback` for hot/expensive
  renders — not blanket-applied (React 19 + compiler-friendly code first).
- Lazy-load route-level and heavy components (`React.lazy` / dynamic import).
  Heavy deps to watch: `exceljs`, `jspdf`, `jspdf-autotable`, `react-select`,
  `react-datepicker` — load on demand, not in the main chunk.
- Tree-shaking: import named members, avoid barrel re-exports that pull the world.
- Drop unused deps — `bootstrap-icons` is a removal target.

## Checklist
- [ ] No duplicated component/util logic (extract to `@/lib` or `@/hooks`)
- [ ] Heavy libs code-split / lazy
- [ ] No unnecessary re-renders in lists/tables
- [ ] No dead imports/files
- [ ] Bundle size not regressed (compare `vite build` output)

## Exit criteria
`vite build` succeeds; no obvious duplicate work; heavy paths lazy.
