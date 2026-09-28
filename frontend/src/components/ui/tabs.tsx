import * as React from "react";
import {
    Tabs as MuiTabs,
    Tab as MuiTab,
    TabProps as MuiTabProps,
    Box,
} from "@mui/material";
import { cn } from "@/lib/utils";

interface TabsProps {
    value?: string | number;
    defaultValue?: string | number;
    onValueChange?: (value: string | number) => void;
    children: React.ReactNode;
    className?: string;
}

const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
    ({ value, defaultValue, onValueChange, children, className, ...props }, ref) => {
        const [internalValue, setInternalValue] = React.useState(defaultValue || 0);
        const controlledValue = value !== undefined ? value : internalValue;

        const handleChange = (_: React.SyntheticEvent, newValue: string | number) => {
            if (value === undefined) {
                setInternalValue(newValue);
            }
            onValueChange?.(newValue);
        };

        return (
            <Box ref={ref} className={cn("w-full", className)} {...props}>
                <MuiTabs
                    value={controlledValue}
                    onChange={handleChange}
                    sx={{
                        borderBottom: 1,
                        borderColor: "divider",
                    }}
                >
                    {React.Children.toArray(children).find(
                        (child: any) => child?.type?.displayName === "TabsList"
                    )}
                </MuiTabs>
                {React.Children.toArray(children).filter(
                    (child: any) => child?.type?.displayName !== "TabsList"
                )}
            </Box>
        );
    }
);
Tabs.displayName = "Tabs";

function TabsList({
    className,
    children,
    ...props
}: React.ComponentProps<"div">) {
    return (
        <Box
            data-slot="tabs-list"
            className={cn(
                "inline-flex h-9 w-fit items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground",
                className
            )}
            {...props}
            sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backgroundColor: "var(--tb-muted, #f5f5f5)",
                padding: "4px",
                borderRadius: "8px",
            }}
        >
            {children}
        </Box>
    );
}

interface TabsTriggerProps {
    value?: string;
    children: React.ReactNode;
    className?: string;
    disabled?: boolean;
}

const TabsTrigger = React.forwardRef<HTMLButtonElement, TabsTriggerProps>(
    ({ className, children, value, ...props }, ref) => (
        <MuiTab
            ref={ref as React.Ref<HTMLButtonElement & any>}
            data-slot="tabs-trigger"
            value={value || children}
            label={children}
            className={cn(
                "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all cursor-pointer",
                "hover:text-foreground",
                "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                "disabled:pointer-events-none disabled:opacity-50",
                className
            )}
            sx={{
                textTransform: "none",
                fontSize: "0.875rem",
                fontWeight: 500,
                padding: "6px 12px",
                minHeight: "36px",
                "&.Mui-selected": {
                    backgroundColor: "var(--tb-card, #ffffff)",
                    color: "var(--tb-foreground, #000000)",
                    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
                },
                "&:hover": {
                    color: "var(--tb-foreground, #000000)",
                },
            }}
            {...(props as any)}
        />
    )
);
TabsTrigger.displayName = "TabsTrigger";

interface TabsContentProps {
    value?: string;
    className?: string;
    children: React.ReactNode;
}

const TabsContent = React.forwardRef<HTMLDivElement, TabsContentProps>(
    ({ value, className, children, ...props }, ref) => (
        <Box
            ref={ref}
            data-slot="tabs-content"
            role="tabpanel"
            hidden={false}
            className={cn("flex-1 outline-none", className)}
            sx={{
                display: "flex",
                flex: 1,
                outline: "none",
            }}
            {...props}
        >
            {children}
        </Box>
    )
);
TabsContent.displayName = "TabsContent";

export { Tabs, TabsList, TabsTrigger, TabsContent };
