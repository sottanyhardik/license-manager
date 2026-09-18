import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
    return (
        <input
            type={type}
            data-slot="input"
            className={cn(
                "flex h-10 w-full min-w-0 rounded-lg border border-input bg-card px-3 py-2 text-sm shadow-sm transition-[color,box-shadow,border-color] outline-none",
                "file:inline-flex file:border-0 file:bg-transparent file:text-sm file:font-medium",
                "placeholder:text-muted-foreground",
                "hover:border-input/80",
                "focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-[3px] focus-visible:shadow",
                "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-muted",
                "aria-invalid:border-destructive aria-invalid:ring-destructive/30",
                className
            )}
            {...props}
        />
    );
}

export { Input };
