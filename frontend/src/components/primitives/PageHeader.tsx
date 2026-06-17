import React from "react";

/**
 * PageHeader — Tabler-style page header.
 *
 *   <PageHeader
 *     pretitle="Operations"
 *     title="Allotments"
 *     description="Manage incoming allotments and their licence allocations"
 *     actions={(
 *       <>
 *         <button className="btn btn-outline-secondary btn-sm">Export</button>
 *         <button className="btn btn-primary btn-sm">+ New</button>
 *       </>
 *     )}
 *   />
 */
export default function PageHeader({
    pretitle,
    title,
    description,
    actions,
    children,
}: {
    pretitle?: React.ReactNode;
    title?: React.ReactNode;
    description?: React.ReactNode;
    actions?: React.ReactNode;
    children?: React.ReactNode;
}) {
    return (
        <div className="page-header">
            <div style={{ minWidth: 0 }}>
                {pretitle && <div className="page-pretitle">{pretitle}</div>}
                {title && <h1>{title}</h1>}
                {description && (
                    <div className="text-secondary" style={{ marginTop: 4, fontSize: "13.5px" }}>
                        {description}
                    </div>
                )}
                {children}
            </div>
            {actions && (
                <div className="page-actions">{actions}</div>
            )}
        </div>
    );
}
