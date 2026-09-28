import * as React from "react";
import {
    Dialog as MuiDialog,
    DialogTitle as MuiDialogTitle,
    DialogContent as MuiDialogContent,
    DialogActions as MuiDialogActions,
    IconButton,
    DialogProps as MuiDialogProps,
} from "@mui/material";
import { X as XIcon } from "lucide-react";
import { cn } from "@/lib/utils";

// Wrapper component for MUI Dialog
interface DialogProps {
    open: boolean;
    onOpenChange?: (open: boolean) => void;
    children: React.ReactNode;
    maxWidth?: "xs" | "sm" | "md" | "lg" | "xl" | false;
}

const Dialog = React.forwardRef<HTMLDivElement, DialogProps>(
    ({ open, onOpenChange, children, maxWidth = "sm" }, ref) => {
        return (
            <MuiDialog
                ref={ref}
                open={open}
                onClose={() => onOpenChange?.(false)}
                maxWidth={maxWidth}
                fullWidth
                slotProps={{
                    paper: {
                        sx: {
                            borderRadius: "var(--tb-r-lg, 8px)",
                            boxShadow: "0 10px 40px rgba(0,0,0,0.15)",
                        },
                    },
                }}
            >
                {children}
            </MuiDialog>
        );
    }
);
Dialog.displayName = "Dialog";

// DialogTrigger - not used with MUI Dialog (control open state from parent)
const DialogTrigger = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
    (props, ref) => <button ref={ref} {...props} />
);
DialogTrigger.displayName = "DialogTrigger";

// DialogPortal - MUI Dialog handles this automatically
const DialogPortal = ({ children }: { children: React.ReactNode }) => <>{children}</>;

// DialogClose - button that closes the dialog
const DialogClose = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { onClick?: () => void }
>(({ onClick, ...props }, ref) => (
    <button
        ref={ref}
        onClick={onClick}
        {...props}
    />
));
DialogClose.displayName = "DialogClose";

// DialogOverlay - MUI Dialog's backdrop is built-in
const DialogOverlay = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ ...props }, ref) => <div ref={ref} {...props} />);
DialogOverlay.displayName = "DialogOverlay";

// DialogContent wrapper for MUI DialogContent
const DialogContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & {
        showCloseButton?: boolean;
    }
>(({ className, children, showCloseButton = true, ...props }, ref) => (
    <MuiDialogContent
        ref={ref}
        className={cn("p-6", className)}
        {...props}
    >
        {children}
        {showCloseButton && (
            <IconButton
                aria-label="close"
                onClick={(e) => {
                    e.currentTarget.closest('[role="dialog"]')?.dispatchEvent(
                        new KeyboardEvent("keydown", { key: "Escape" })
                    );
                }}
                sx={{
                    position: "absolute",
                    right: 8,
                    top: 8,
                    color: "text.secondary",
                    "&:hover": {
                        backgroundColor: "action.hover",
                    },
                }}
            >
                <XIcon className="size-4" />
            </IconButton>
        )}
    </MuiDialogContent>
));
DialogContent.displayName = "DialogContent";

function DialogHeader({ className, ...props }: React.ComponentProps<"div">) {
    return (
        <div
            data-slot="dialog-header"
            className={cn("flex flex-col gap-1.5 text-left", className)}
            {...props}
        />
    );
}

function DialogFooter({ className, ...props }: React.ComponentProps<"div">) {
    return (
        <MuiDialogActions
            className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end px-6 py-3", className)}
            {...props}
        />
    );
}

const DialogTitle = React.forwardRef<HTMLHeadingElement, React.ComponentProps<"h2">>(
    ({ className, ...props }, ref) => (
        <MuiDialogTitle
            ref={ref}
            className={cn("text-base font-semibold tracking-tight", className)}
            {...props}
        />
    )
);
DialogTitle.displayName = "DialogTitle";

function DialogDescription({ className, ...props }: React.ComponentProps<"div">) {
    return (
        <div
            data-slot="dialog-description"
            className={cn("text-muted-foreground text-sm", className)}
            {...props}
        />
    );
}

export {
    Dialog,
    DialogPortal,
    DialogOverlay,
    DialogClose,
    DialogTrigger,
    DialogContent,
    DialogHeader,
    DialogFooter,
    DialogTitle,
    DialogDescription,
};
