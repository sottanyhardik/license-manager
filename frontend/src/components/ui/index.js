// Legacy UI primitives barrel (Tabler-inspired). Kept working during the
// shadcn/Tailwind migration. New code should import shadcn primitives directly
// from "@/components/ui/<name>". These re-exports point at ../primitives/* and
// are removed in Phase 4 once all pages are migrated.

export { default as Surface }        from "../primitives/Surface";
export { default as EmptyState }     from "../primitives/EmptyState";
export { default as Skeleton }       from "../primitives/Skeleton";
export { default as IconChip }       from "../primitives/IconChip";
export { default as StatusBadge }    from "../primitives/StatusBadge";
export { default as SectionHeader }  from "../primitives/SectionHeader";
export { default as PageHeader }     from "../primitives/PageHeader";
export { default as EntityCard }     from "../primitives/EntityCard";
export { default as DetailTable }    from "../primitives/DetailTable";
export { default as Button }         from "../primitives/Button";
export { default as Toolbar, ToolbarGroup, ToolbarSpacer, ToolbarDivider } from "../primitives/Toolbar";
export { default as FilterBar, FilterField } from "../primitives/FilterBar";
export { default as StatCard }       from "../primitives/StatCard";

// Backwards-compatible Card family.
export { Card, CardHeader, CardBody, CardFooter } from "../primitives/Card";
