import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
    icon: LucideIcon;
    title: string;
    description?: string;
    action?: React.ReactNode;
    className?: string;
}

export default function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
    return (
        <div className={cn("flex flex-col items-center px-6 py-12 text-center", className)}>
            <Icon className="mb-3 size-9 text-muted-foreground/40" />
            <div className="text-sm font-semibold text-muted-foreground">{title}</div>
            {description && <p className="mt-1 max-w-xs text-xs leading-relaxed text-muted-foreground/80">{description}</p>}
            {action && <div className="mt-4">{action}</div>}
        </div>
    );
}
