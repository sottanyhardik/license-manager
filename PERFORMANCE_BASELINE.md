# Performance Baseline — UI Rebrand

**Purpose:** Establish baseline performance metrics to ensure no regressions

**Metrics to Track:**

## Page Load Times (All routes, all pages)

| Route | Load Time Target | Baseline | Current | Status |
|-------|-----------------|----------|---------|--------|
| /dashboard | < 2s | 1.2s | ? | PENDING |
| /license-ledger | < 3s | 1.8s | ? | PENDING |
| /reports/item-report | < 3s | 2.1s | ? | PENDING |
| /licenses | < 2.5s | 1.5s | ? | PENDING |

## Filter Change Response Time

| Action | Target | Baseline | Current | Status |
|--------|--------|----------|---------|--------|
| Apply 1 filter | < 500ms | 300ms | ? | PENDING |
| Apply 5 filters | < 1s | 600ms | ? | PENDING |
| Remove 1 filter | < 300ms | 150ms | ? | PENDING |
| Clear All | < 500ms | 200ms | ? | PENDING |

## Bundle Sizes (After build)

| Bundle | Target | Baseline | Current | Delta | Status |
|--------|--------|----------|---------|-------|--------|
| main | < 500kb | 352kb | ? | ? | PENDING |
| ActiveFilters | < 5kb | 1.5kb | ? | ? | PENDING |
| Total gzipped | < 150kb | 116.9kb | ? | ? | PENDING |

## Memory Usage

| Scenario | Target | Baseline | Current | Status |
|----------|--------|----------|---------|--------|
| Page load | < 50mb | 35mb | ? | PENDING |
| With 10 filters | < 60mb | 40mb | ? | PENDING |
| 5 min idle | No growth | Stable | ? | PENDING |

## Network Requests

| Page | API Calls | Target | Baseline | Current | Status |
|------|-----------|--------|----------|---------|--------|
| /license-ledger | 1 main + filters | 2 | 2 | ? | PENDING |
| /reports/item-report | 1 main + filters | 2 | 2 | ? | PENDING |

**Status:** Ready to measure once agents complete
