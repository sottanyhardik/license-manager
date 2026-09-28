import * as React from "react";
import { Skeleton as MuiSkeleton, SkeletonProps as MuiSkeletonProps } from "@mui/material";
import { cn } from "@/lib/utils";

const Skeleton = React.forwardRef<HTMLDivElement, MuiSkeletonProps>(
    ({ className, variant = "rectangular", ...props }, ref) => (
        <MuiSkeleton
            ref={ref}
            data-slot="skeleton"
            variant={variant}
            className={cn("bg-muted rounded-md", className)}
            sx={{
                backgroundColor: "var(--tb-muted, #f5f5f5)",
                borderRadius: "var(--tb-r-md, 6px)",
                animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
                "@keyframes pulse": {
                    "0%, 100%": {
                        opacity: 1,
                    },
                    "50%": {
                        opacity: 0.5,
                    },
                },
            }}
            {...props}
        />
    )
);
Skeleton.displayName = "Skeleton";

export { Skeleton };
