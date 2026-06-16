/*
 * FilterBar — flat row of labelled filter fields with consistent spacing.
 *
 *   <FilterBar>
 *     <FilterField label="Status">
 *       <select className="form-select form-select-sm">…</select>
 *     </FilterField>
 *     <FilterField label="Port">
 *       <ReactSelect …/>
 *     </FilterField>
 *     <FilterBar.Spacer />
 *     <Button variant="outline-secondary" size="sm" icon="x-lg">Clear</Button>
 *   </FilterBar>
 */
export default function FilterBar({ children, className = "", style }) {
    return (
        <div className={`filter-bar ${className}`.trim()} style={style}>
            {children}
        </div>
    );
}

export function FilterField({ label, children, style }) {
    return (
        <div className="filter-field" style={style}>
            {label && <label>{label}</label>}
            {children}
        </div>
    );
}

function FilterSpacer() {
    return <div style={{ flex: 1 }} />;
}

FilterBar.Field = FilterField;
FilterBar.Spacer = FilterSpacer;
