import React from "react";
import { cn } from "@/lib/utils";

export default function PageHeader({
    pretitle, title, description, actions, children, className,
}: {
    pretitle?: React.ReactNode; title?: React.ReactNode;
    description?: React.ReactNode; actions?: React.ReactNode;
    children?: React.ReactNode; className?: string;
}) {
    return (
        <div className={cn("page-header", className)}>
            <div className="min-w-0 flex-1">
                {pretitle && <div className="page-pretitle">{pretitle}</div>}
                {title && <h1 className="text-2xl font-bold leading-tight tracking-tight text-foreground">{title}</h1>}
                {description && <p className="mt-1 text-[13px] text-muted-foreground">{description}</p>}
                {children}
            </div>
            {actions && <div className="page-actions">{actions}</div>}
        </div>
    );
}
