# Dependency and module map

The current dependency picture is a Django/DRF modular monolith plus React/Vite frontend. Existing audit evidence should be treated as source references, not competing architectural standards:

- `docs/discovery/01_SYSTEM_MODULE_MAP.md` and `02_SYSTEM_DEPENDENCY_GRAPH.md` are historical discovery inputs.
- `docs/architecture/CALCULATION_OWNERSHIP.md` is source for calculation ownership entries, subject to revalidation.
- `docs/audit/phase-*.md` contains phase-specific evidence and must not be read as a single current specification.
- `docs/frontend-migration/` contains detailed route/API-callsite inventories from a prior frontend effort.

The authoritative future boundary map is `../04-target-architecture/target-architecture.md`. Rebuild task owners must expand source-level callers only after the mandated index is available.

