# TypeScript Errors - BLOCKING

These 4 errors must be fixed before redesign commits proceed.

## Error 1: AuthContext.tsx - Missing useRef initial value
**File**: `frontend/src/context/AuthContext.tsx:64`
**Error**: `error TS2554: Expected 1 arguments, but got 0.`
**Issue**: `useRef()` requires an initial value in this TypeScript configuration
**Fix**: Change line 64 from:
```typescript
const logoutRef = useRef<(reason?: string) => Promise<void>>();
```
To:
```typescript
const logoutRef = useRef<((reason?: string) => Promise<void>) | null>(null);
```

---

## Error 2: accessibility.test.ts - Missing module
**File**: `frontend/src/test/accessibility.test.ts:9`
**Error**: `error TS2307: Cannot find module 'axe-playwright' or its corresponding type declarations.`
**Issue**: The package `axe-playwright` is imported but not installed
**Fix**: Either:
1. Install the package: `npm install axe-playwright`
2. Or remove the import if not needed (it's not used in the current code)
**Recommendation**: Remove the unused import since `getViolations` is never used

---

## Error 3: accessibility.test.ts - Logic error in comparison
**File**: `frontend/src/test/accessibility.test.ts:103`
**Error**: `error TS2367: This comparison appears to be unintentional because the types '"none"' and '"0px"' have no overlap.`
**Issue**: Line 103 has `|| ` which creates always-true logic. If outlineWidth is 'none', it's !== to '0px'
**Fix**: Change line 103 from:
```typescript
styles.outlineWidth !== 'none' ||
styles.outlineWidth !== '0px' ||
```
To:
```typescript
styles.outlineWidth !== 'none' &&
styles.outlineWidth !== '0px' &&
```

---

## Error 4: accessibility.test.ts - Invalid method on Locator
**File**: `frontend/src/test/accessibility.test.ts:215`
**Error**: `error TS2339: Property 'tagName' does not exist on type 'Locator'.`
**Issue**: Playwright's `Locator` objects don't have a `tagName()` method
**Fix**: Change line 215 from:
```typescript
smallTargets.push(`${await element.tagName()}: "${text}"`);
```
To:
```typescript
smallTargets.push(`${await element.evaluate(el => el.tagName)}: "${text}"`);
```

---

## Action Required

These errors must be fixed BEFORE page redesign agents start committing changes. Once fixed, typecheck will pass and build will be production-ready.

**Next Step**: Apply these fixes and re-run `npm run typecheck` to verify all errors are resolved.
