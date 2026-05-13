/*
 * Toolbar — horizontal action row above tables/lists.
 *
 *   <Toolbar>
 *     <ToolbarGroup>
 *       <Button icon="plus-lg">New</Button>
 *       <Button variant="outline-secondary" icon="download">Excel</Button>
 *     </ToolbarGroup>
 *     <ToolbarSpacer />
 *     <Toolbar.Search value={q} onChange={setQ} placeholder="Search…" />
 *   </Toolbar>
 */
export default function Toolbar({ children, className = "", style }) {
    return (
        <div className={`tb-toolbar ${className}`.trim()} style={style}>
            {children}
        </div>
    );
}

export function ToolbarGroup({ children, label, className = "" }) {
    return (
        <div className={`tb-toolbar-group ${className}`.trim()}>
            {label && <span className="tb-toolbar-label">{label}</span>}
            {children}
        </div>
    );
}

export function ToolbarSpacer() {
    return <div className="tb-toolbar-spacer" />;
}

export function ToolbarDivider() {
    return <div className="tb-toolbar-divider" aria-hidden="true" />;
}

function ToolbarSearch({ value, onChange, placeholder = "Search…", style }) {
    return (
        <div className="input-group input-group-sm" style={{ maxWidth: 280, ...style }}>
            <span className="input-group-text" aria-hidden="true">
                <i className="bi bi-search" />
            </span>
            <input
                type="search"
                className="form-control form-control-sm"
                value={value ?? ""}
                onChange={e => onChange?.(e.target.value)}
                placeholder={placeholder}
                aria-label={placeholder}
            />
        </div>
    );
}

Toolbar.Group = ToolbarGroup;
Toolbar.Spacer = ToolbarSpacer;
Toolbar.Divider = ToolbarDivider;
Toolbar.Search = ToolbarSearch;
