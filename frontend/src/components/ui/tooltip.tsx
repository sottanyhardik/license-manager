import * as React from "react";
import {
    Tooltip as MuiTooltip,
    TooltipProps as MuiTooltipProps,
} from "@mui/material";
import { cn } from "@/lib/utils";

interface TooltipProviderProps {
    delayDuration?: number;
    children: React.ReactNode;
}

function TooltipProvider({ delayDuration = 200, children }: TooltipProviderProps) {
    // MUI Tooltip doesn't require a provider, but we keep this for API compatibility
    return <>{children}</>;
}

interface TooltipProps extends Omit<MuiTooltipProps, "title"> {
    title?: React.ReactNode;
    children: React.ReactElement;
}

const Tooltip = React.forwardRef<HTMLDivElement, TooltipProps>(
    ({ title, children, enterDelay = 200, ...props }, ref) => {
        return (
            <MuiTooltip
                ref={ref}
                data-slot="tooltip"
                title={title}
                enterDelay={enterDelay}
                slotProps={{
                    popper: {
                        sx: {
                            zIndex: 1070,
                        },
                    },
                    tooltip: {
                        sx: {
                            backgroundColor: "var(--tb-foreground, #000000)",
                            color: "var(--tb-background, #ffffff)",
                            fontSize: "0.75rem",
                            padding: "4px 8px",
                            borderRadius: "var(--tb-r-sm, 4px)",
                        },
                    },
                }}
                {...props}
            >
                {children}
            </MuiTooltip>
        );
    }
);
Tooltip.displayName = "Tooltip";

// TooltipTrigger - not needed for MUI Tooltip, children are the trigger
const TooltipTrigger = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ ...props }, ref) => <div ref={ref} {...props} />);
TooltipTrigger.displayName = "TooltipTrigger";

// TooltipContent - not needed for MUI Tooltip, title prop handles this
const TooltipContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => (
    <div ref={ref} className={cn("z-[1070] w-fit rounded-md bg-foreground px-2.5 py-1 text-xs text-background shadow-md", className)} {...props}>
        {children}
    </div>
));
TooltipContent.displayName = "TooltipContent";

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider };
