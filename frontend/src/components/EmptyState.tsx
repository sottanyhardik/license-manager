import React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface EmptyStateProps {
    icon: LucideIcon;
    title: string;
    description?: string;
    action?: React.ReactNode;
    className?: string;
    /** Visual weight: "default" = compact table empty state, "page" = full-page empty */
    size?: "default" | "page";
}

export default function EmptyState({ icon: Icon, title, description, action, className, size = "default" }: EmptyStateProps) {
    const isPage = size === "page";
    return (
        <div
            className={cn(
                "flex flex-col items-center text-center",
                isPage ? "px-8 py-20" : "px-6 py-12",
                className
            )}
        >
            {/* Icon container with subtle ring */}
            <span
                className={cn(
                    "mb-4 inline-flex items-center justify-center rounded-2xl border border-border/60 bg-muted/60",
                    isPage ? "size-16" : "size-11"
                )}
            >
                <Icon
                    className={cn(
                        "text-muted-foreground/50",
                        isPage ? "size-8" : "size-5"
                    )}
                    strokeWidth={1.5}
                />
            </span>
            <p
                className={cn(
                    "font-semibold text-foreground",
                    isPage ? "text-base" : "text-sm"
                )}
            >
                {title}
            </p>
            {description && (
                <p
                    className={cn(
                        "mt-1.5 max-w-xs leading-relaxed text-muted-foreground",
                        isPage ? "text-sm" : "text-xs"
                    )}
                >
                    {description}
                </p>
            )}
            {action && <div className="mt-5">{action}</div>}
        </div>
    );
}
