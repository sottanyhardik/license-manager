import { Loader2Icon } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface LoadingStateProps {
    variant: "skeleton-rows" | "spinner" | "page";
    rows?: number;
    label?: string;
}

export function LoadingState({ variant, rows = 5, label = "Loading" }: LoadingStateProps) {
    if (variant === "skeleton-rows") {
        return (
            <div role="status" aria-label={label} className="space-y-2">
                {Array.from({ length: rows }, (_, i) => (
                    <Skeleton key={i} aria-hidden="true" className="h-8 w-full" />
                ))}
            </div>
        );
    }
    return (
        <div role="status" aria-label={label} className={cn("flex items-center justify-center gap-2 text-muted-foreground", variant === "page" ? "min-h-[50vh]" : "py-6")}>
            <Loader2Icon aria-hidden="true" className="size-5 animate-spin motion-reduce:animate-none" />
            <span className="text-sm">{label}</span>
        </div>
    );
}
