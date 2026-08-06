/**
 * Display Dataset envelope convention — Phase 2A of the export-consistency
 * initiative. Mirrors `backend/apps/core/reports/envelope.py`.
 *
 * Not a runtime contract enforced by these types alone (TypeScript types
 * vanish at build time) — the backend's `validate_envelope()` is the actual
 * shape guard. This type exists so report-specific response types can
 * document "this matches the Display Dataset convention" the same way
 * `pages/license-balance/types.ts` hand-writes one exact JSON shape rather
 * than generating types from the API (no codegen in this codebase).
 *
 * `TRow` is the row shape; `TSummary` is the report's own summary shape.
 * The row list itself keeps the report's own existing plural key name
 * (e.g. `licenses`, `items`) rather than a generic `rows` — every report
 * already has its own name for this, and renaming it would be a breaking
 * API change for no benefit. Report-specific types should extend this
 * shape's `summary`/`meta` fields directly rather than trying to use this
 * generic via structural inheritance of a differently-named row key.
 */
export interface ReportEnvelope<TSummary> {
    summary: TSummary;
    meta?: {
        generated_at?: string;
        filters_applied?: Record<string, unknown>;
        report_name?: string;
    };
}
