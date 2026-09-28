import * as React from "react";
import {
    Alert as MuiAlert,
    AlertTitle as MuiAlertTitle,
    AlertProps as MuiAlertProps,
} from "@mui/material";
import { cn } from "@/lib/utils";

type AlertVariant = "default" | "destructive" | "warning" | "success" | "info";

interface AlertProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: AlertVariant;
}

// Map our variant names to MUI Alert severity
const variantMap: Record<AlertVariant, MuiAlertProps["severity"]> = {
    default: "info",
    destructive: "error",
    warning: "warning",
    success: "success",
    info: "info",
};

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(
    ({ className, variant = "default", children, ...props }, ref: React.Ref<HTMLDivElement>) => {
        const severity = variantMap[variant] || "info";
        return (
            <MuiAlert
                ref={ref}
                data-slot="alert"
                role="alert"
                severity={severity}
                className={cn("w-full", className)}
                sx={{
                    borderRadius: "var(--tb-r-lg, 8px)",
                    padding: "12px 16px",
                    fontSize: "0.875rem",
                    "& .MuiAlert-icon": {
                        marginRight: "12px",
                    },
                    "& .MuiAlertTitle-root": {
                        marginBottom: "4px",
                    },
                }}
                {...(props as any)}
            >
                {children}
            </MuiAlert>
        );
    }
);
Alert.displayName = "Alert";

const AlertTitle = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <MuiAlertTitle
            ref={ref}
            data-slot="alert-title"
            className={cn("font-medium leading-none tracking-tight", className)}
            sx={{
                marginBottom: "4px",
                fontWeight: 600,
            }}
            {...props}
        />
    )
);
AlertTitle.displayName = "AlertTitle";

const AlertDescription = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <div
            ref={ref}
            data-slot="alert-description"
            className={cn("grid justify-items-start gap-1 text-sm [&_p]:leading-relaxed", className)}
            {...props}
        />
    )
);
AlertDescription.displayName = "AlertDescription";

export { Alert, AlertTitle, AlertDescription };
