import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
    "inline-flex items-center justify-center gap-1 rounded-md border px-2 py-0.5 text-xs font-medium w-fit whitespace-nowrap shrink-0 [&>svg]:size-3 transition-colors overflow-hidden",
    {
        variants: {
            variant: {
                default:
                    "border-transparent bg-primary/10 text-primary",
                secondary:
                    "border-transparent bg-secondary text-secondary-foreground",
                destructive:
                    "border-transparent bg-destructive/10 text-destructive",
                success:
                    "border-transparent bg-success/10 text-success",
                warning:
                    "border-transparent bg-warning/10 text-warning",
                info:
                    "border-transparent bg-info/10 text-info",
                outline: "text-foreground border-border",
            },
        },
        defaultVariants: {
            variant: "default",
        },
    }
);

function Badge({
    className,
    variant,
    asChild = false,
    ...props
}: React.ComponentProps<"span"> &
    VariantProps<typeof badgeVariants> & { asChild?: boolean }) {
    const Comp = asChild ? Slot : "span";
    return (
        <Comp
            data-slot="badge"
            className={cn(badgeVariants({ variant }), className)}
            {...props}
        />
    );
}

export { Badge, badgeVariants };
