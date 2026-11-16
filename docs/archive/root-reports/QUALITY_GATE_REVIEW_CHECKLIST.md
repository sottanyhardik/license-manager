# Quality Gate Review Checklist for Page Redesigns

## For Each Commit Containing Page Redesigns

### Phase 1: Automated Quality Gates
- [ ] Run `npm run lint` on changed files - check for new errors (warnings acceptable)
- [ ] Run `npm run typecheck` - check for new TypeScript errors only
- [ ] Run `npm run build` - verify build succeeds
- [ ] Check for `console.log()`, `debugger`, `console.error()` statements
- [ ] Check for hardcoded values (colors, sizes, strings that should be tokens/constants)
- [ ] Verify all imports are valid and no files were accidentally deleted
- [ ] Check git diff for file deletions that might break callers

### Phase 2: Code Quality Inspection
For each changed `.tsx/.ts` file:
- [ ] No React hooks rules violations (dependencies, stale closures)
- [ ] No missing error handling for API calls
- [ ] No N+1 queries or redundant API calls
- [ ] Props properly typed (no implicit `any`)
- [ ] Event handlers properly bound or memoized
- [ ] Components properly memoized if needed (avoid unnecessary re-renders)
- [ ] No direct localStorage/sessionStorage manipulation (use context)
- [ ] No hardcoded auth tokens or sensitive data

### Phase 3: Design System Adherence
- [ ] Uses only Tabler/shadcn components (no ad-hoc styled divs)
- [ ] Uses Tailwind v4 tokens for colors/spacing/sizes
- [ ] Uses lucide-react only for icons (no Tabler icons)
- [ ] Uses sonner for toasts (not custom notifications)
- [ ] Consistent button sizing and styling
- [ ] Consistent spacing patterns (gap, padding, margin)
- [ ] No hardcoded hex colors
- [ ] Dark mode support (check with dark mode emulation)

### Phase 4: Functional Regression Tests
For the redesigned page:
- [ ] Navigation still works (sidebar/breadcrumbs/tabs)
- [ ] Search filters still function properly
- [ ] Forms submit correctly
- [ ] CRUD operations work (create, read, update, delete)
- [ ] Sorting/pagination work if present
- [ ] Exports (PDF, Excel) work if present
- [ ] File uploads work if present
- [ ] Permissions still enforced (user can't access restricted data)
- [ ] Authentication required (redirect to login if needed)
- [ ] Session expiration handled (logout works)
- [ ] Calculations still correct (if financial page)
- [ ] No 404s in console
- [ ] No JS errors in console (only pre-existing ones acceptable)

### Phase 5: Accessibility Check
- [ ] Keyboard navigation works (Tab, Enter, Escape)
- [ ] Focus indicators visible
- [ ] Color contrast adequate (WCAG AA)
- [ ] Form labels properly associated
- [ ] No missing alt text for critical images
- [ ] No color-only indicators (must have text/icon backup)

### Phase 6: Performance Check
- [ ] No massive bundle size increase
- [ ] No new N+1 queries
- [ ] No infinite loops in useEffect
- [ ] Images lazy-loaded where appropriate
- [ ] No heavy computations in render path

---

## Blocker Criteria (Must Fix Before Merge)
Any of these are immediate blockers:
- ❌ New TypeScript errors (pre-existing 4 exceptions OK)
- ❌ New ESLint errors in rebrand files (not test files)
- ❌ Build fails
- ❌ console.log/debugger statements in production code
- ❌ Broken imports preventing page load
- ❌ Hardcoded colors/tokens instead of design system values
- ❌ Page completely non-functional
- ❌ WCAG AA contrast violations in redesign

## Non-Blocker (Nice-to-Have Fixes)
- Unused variable warnings in test files
- Pre-existing TypeScript errors
- Minor console messages (if from dependencies)

---

## Review Report Template

For each commit with page changes:

```markdown
### Commit: [SHA] - [Message]

**Files Changed**: [list redesigned pages]

**Quality Gate Results:**
- ESLint: ✅/❌ [details]
- TypeScript: ✅/❌ [new errors if any]
- Build: ✅/❌ [time]
- Console logs: ✅/❌ [found if any]
- Hardcoded values: ✅/❌ [found if any]
- Broken imports: ✅/❌ [found if any]

**Code Quality:**
- ✅/❌ React best practices
- ✅/❌ Design system compliance
- ✅/❌ Error handling

**Functional Regression:**
- ✅/❌ Navigation works
- ✅/❌ Filters/search works
- ✅/❌ CRUD operations work
- ✅/❌ Exports work
- ✅/❌ No console errors

**Accessibility:**
- ✅/❌ Keyboard navigation
- ✅/❌ Contrast ratios
- ✅/❌ Focus indicators

**Verdict**: ✅ APPROVED / ⚠️ APPROVED WITH NITS / ❌ CHANGES REQUESTED

**Issues Found:**
[List any blockers or suggestions]
```
