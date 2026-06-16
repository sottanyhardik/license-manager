import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { CheckIcon, ChevronDownIcon, ChevronUpIcon } from "lucide-react";

import { cn } from "@/lib/utils";

const Select = SelectPrimitive.Root;
const SelectGroup = SelectPrimitive.Group;
const SelectValue = SelectPrimitive.Value;

function SelectTrigger({
    className,
    size = "default",
    children,
    ...props
}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {
    size?: "sm" | "default";
}) {
    return (
        <SelectPrimitive.Trigger
            data-slot="select-trigger"
            data-size={size}
            className={cn(
                "flex w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-3 py-2 text-sm shadow-sm transition-[color,box-shadow] outline-none cursor-pointer",
                "data-[size=default]:h-9 data-[size=sm]:h-8",
                "placeholder:text-muted-foreground [&_span]:line-clamp-1",
                "focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-[3px]",
                "disabled:cursor-not-allowed disabled:opacity-50",
                "data-[placeholder]:text-muted-foreground [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:opacity-60",
                className
            )}
            {...props}
        >
            {children}
            <SelectPrimitive.Icon asChild>
                <ChevronDownIcon className="size-4 opacity-60" />
            </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
    );
}

function SelectContent({
    className,
    children,
    position = "popper",
    ...props
}: React.ComponentProps<typeof SelectPrimitive.Content>) {
    return (
        <SelectPrimitive.Portal>
            <SelectPrimitive.Content
                data-slot="select-content"
                className={cn(
                    "relative z-[1060] max-h-96 min-w-[8rem] overflow-hidden rounded-md border bg-popover text-popover-foreground shadow-md",
                    "data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
                    position === "popper" &&
                        "data-[side=bottom]:translate-y-1 data-[side=top]:-translate-y-1",
                    className
                )}
                position={position}
                {...props}
            >
                <SelectPrimitive.ScrollUpButton className="flex items-center justify-center py-1">
                    <ChevronUpIcon className="size-4" />
                </SelectPrimitive.ScrollUpButton>
                <SelectPrimitive.Viewport
                    className={cn(
                        "p-1",
                        position === "popper" &&
                            "h-[var(--radix-select-trigger-height)] w-full min-w-[var(--radix-select-trigger-width)]"
                    )}
                >
                    {children}
                </SelectPrimitive.Viewport>
                <SelectPrimitive.ScrollDownButton className="flex items-center justify-center py-1">
                    <ChevronDownIcon className="size-4" />
                </SelectPrimitive.ScrollDownButton>
            </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
    );
}

function SelectItem({
    className,
    children,
    ...props
}: React.ComponentProps<typeof SelectPrimitive.Item>) {
    return (
        <SelectPrimitive.Item
            data-slot="select-item"
            className={cn(
                "relative flex w-full cursor-pointer select-none items-center gap-2 rounded-sm py-1.5 pl-2 pr-8 text-sm outline-none",
                "focus:bg-accent focus:text-accent-foreground",
                "data-[disabled]:pointer-events-none data-[disabled]:opacity-50",
                className
            )}
            {...props}
        >
            <span className="absolute right-2 flex size-3.5 items-center justify-center">
                <SelectPrimitive.ItemIndicator>
                    <CheckIcon className="size-4" />
                </SelectPrimitive.ItemIndicator>
            </span>
            <SelectPrimitive.ItemText>{children}</SelectPrimitive.ItemText>
        </SelectPrimitive.Item>
    );
}

function SelectLabel({
    className,
    ...props
}: React.ComponentProps<typeof SelectPrimitive.Label>) {
    return (
        <SelectPrimitive.Label
            className={cn("px-2 py-1.5 text-xs text-muted-foreground", className)}
            {...props}
        />
    );
}

function SelectSeparator({
    className,
    ...props
}: React.ComponentProps<typeof SelectPrimitive.Separator>) {
    return (
        <SelectPrimitive.Separator
            className={cn("-mx-1 my-1 h-px bg-border", className)}
            {...props}
        />
    );
}

export {
    Select,
    SelectGroup,
    SelectValue,
    SelectTrigger,
    SelectContent,
    SelectItem,
    SelectLabel,
    SelectSeparator,
};
