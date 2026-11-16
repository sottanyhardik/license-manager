import type { ReactNode } from "react";
import { InboxIcon, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface EmptyStateProps {
    title: string;
    description?: string;
    icon?: LucideIcon;
    /** At most one action. */
    action?: ReactNode;
    size?: "inline" | "page";
}

export function EmptyState({ title, description, icon: Icon = InboxIcon, action, size = "inline" }: EmptyStateProps) {
    return (
        <div role="status" className={cn("flex flex-col items-center justify-center text-center text-muted-foreground", size === "page" ? "py-20" : "py-8")}>
            <Icon aria-hidden="true" className={cn("mb-2 opacity-60", size === "page" ? "size-10" : "size-6")} />
            <p className="text-sm font-medium text-foreground">{title}</p>
            {description && <p className="mt-1 max-w-sm text-sm">{description}</p>}
            {action && <div className="mt-3">{action}</div>}
        </div>
    );
}
