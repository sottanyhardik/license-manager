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
                isPage ? "px-8 py-24" : "px-6 py-14",
                className
            )}
        >
            {/* Icon container with subtle ring */}
            <span
                className={cn(
                    "mb-5 inline-flex items-center justify-center rounded-xl border border-border/60 bg-muted/50",
                    isPage ? "size-18" : "size-12"
                )}
            >
                <Icon
                    className={cn(
                        "text-muted-foreground/60",
                        isPage ? "size-9" : "size-5"
                    )}
                    strokeWidth={1.5}
                />
            </span>
            <p
                className={cn(
                    "font-bold text-foreground",
                    isPage ? "text-lg" : "text-base"
                )}
            >
                {title}
            </p>
            {description && (
                <p
                    className={cn(
                        "mt-2 max-w-sm leading-relaxed text-muted-foreground",
                        isPage ? "text-sm" : "text-xs"
                    )}
                >
                    {description}
                </p>
            )}
            {action && <div className="mt-6">{action}</div>}
        </div>
    );
}
