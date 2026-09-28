import * as React from "react";
import { Box } from "@mui/material";
import { cn } from "@/lib/utils";

interface TabsProps {
    value?: string | number;
    defaultValue?: string | number;
    onValueChange?: (value: string | number) => void;
    children: React.ReactNode;
    className?: string;
}

interface TabsContextType {
    value: string | number;
}

const TabsContext = React.createContext<TabsContextType | undefined>(undefined);

const Tabs = React.forwardRef<HTMLDivElement, TabsProps>(
    ({ value, defaultValue, onValueChange, children, className, ...props }, ref) => {
        const [internalValue, setInternalValue] = React.useState(defaultValue || 0);
        const controlledValue = value !== undefined ? value : internalValue;

        const handleChange = (newValue: string | number) => {
            if (value === undefined) {
                setInternalValue(newValue);
            }
            onValueChange?.(newValue);
        };

        const childArray = React.Children.toArray(children);
        const tabsList = childArray.find(
            (child: any) => child?.type?.displayName === "TabsList"
        ) as any;
        const tabsContent = childArray.filter(
            (child: any) => child?.type?.displayName !== "TabsList"
        );

        // Extract trigger children from TabsList
        const triggers = React.Children.toArray(tabsList?.props?.children || []);

        return (
            <TabsContext.Provider value={{ value: controlledValue }}>
                <Box ref={ref} className={cn("w-full", className)} {...props}>
                    {/* Custom tabs list rendering without MUI Tabs */}
                    <div
                        role="tablist"
                        className="inline-flex h-9 w-fit items-center justify-center rounded-lg bg-muted p-1 text-muted-foreground"
                        style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            backgroundColor: "var(--tb-muted, #f5f5f5)",
                            padding: "4px",
                            borderRadius: "8px",
                            borderBottom: "1px solid var(--tb-border, #e5e7eb)",
                        }}
                    >
                        {React.Children.map(triggers, (trigger: any) => {
                            const triggerValue = trigger?.props?.value || trigger?.props?.children;
                            const isSelected = controlledValue === triggerValue;
                            return React.cloneElement(trigger, {
                                key: triggerValue,
                                role: "tab",
                                "aria-selected": isSelected,
                                onClick: () => handleChange(triggerValue),
                            } as any);
                        })}
                    </div>
                    {React.Children.map(tabsContent, (content: any) => {
                        const contentValue = content?.props?.value;
                        const isVisible = controlledValue === contentValue;
                        return React.cloneElement(content, {
                            key: contentValue,
                            hidden: !isVisible,
                            style: {
                                ...(content?.props?.style || {}),
                                display: isVisible ? (content?.props?.style?.display || "flex") : "none",
                            },
                        } as any);
                    })}
                </Box>
            </TabsContext.Provider>
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
    ({ className, children, value, disabled, ...props }, ref) => (
        <button
            ref={ref}
            data-slot="tabs-trigger"
            type="button"
            disabled={disabled}
            className={cn(
                "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-all cursor-pointer",
                "hover:text-foreground",
                "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40",
                "disabled:pointer-events-none disabled:opacity-50",
                "aria-selected:bg-background aria-selected:text-foreground aria-selected:shadow-sm",
                className
            )}
            style={{
                textTransform: "none",
                fontSize: "0.875rem",
                fontWeight: 500,
                padding: "6px 12px",
                minHeight: "36px",
            }}
            {...(props as any)}
        >
            {children}
        </button>
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
