import * as React from "react"
import {
    Menu as MuiMenu,
    MenuItem as MuiMenuItem,
    MenuItemProps as MuiMenuItemProps,
    Divider,
    ListItemIcon,
    ListItemText,
} from "@mui/material"
import { Check, ChevronRight, Circle } from "lucide-react"
import { cn } from "@/lib/utils"

interface DropdownMenuProps {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    children: React.ReactNode;
}

// DropdownMenu is now a context-based wrapper for consistency
const DropdownMenuContext = React.createContext<{
    anchorEl: HTMLElement | null;
    setAnchorEl: (el: HTMLElement | null) => void;
    open: boolean;
    setOpen: (open: boolean) => void;
}>({
    anchorEl: null,
    setAnchorEl: () => {},
    open: false,
    setOpen: () => {},
});

function DropdownMenu({ open: controlledOpen, onOpenChange, children }: DropdownMenuProps) {
    const [anchorEl, setAnchorEl] = React.useState<HTMLElement | null>(null);
    const [internalOpen, setInternalOpen] = React.useState(false);

    const isControlled = controlledOpen !== undefined;
    const open = isControlled ? controlledOpen : internalOpen;

    const handleSetOpen = (newOpen: boolean) => {
        if (!isControlled) {
            setInternalOpen(newOpen);
        }
        onOpenChange?.(newOpen);
    };

    return (
        <DropdownMenuContext.Provider value={{ anchorEl, setAnchorEl, open, setOpen: handleSetOpen }}>
            {children}
        </DropdownMenuContext.Provider>
    );
}

// DropdownMenuTrigger
const DropdownMenuTrigger = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
    ({ onClick, ...props }, ref) => {
        const { setAnchorEl, setOpen } = React.useContext(DropdownMenuContext);

        return (
            <button
                ref={ref}
                onClick={(e) => {
                    setAnchorEl(e.currentTarget);
                    setOpen(true);
                    onClick?.(e);
                }}
                {...props}
            />
        );
    }
);
DropdownMenuTrigger.displayName = "DropdownMenuTrigger";

// DropdownMenuContent
const DropdownMenuContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => {
        const { anchorEl, open, setOpen } = React.useContext(DropdownMenuContext);

        return (
            <MuiMenu
                ref={ref as React.Ref<any>}
                anchorEl={anchorEl}
                open={open}
                onClose={() => setOpen(false)}
                className={cn("z-50", className)}
                slotProps={{
                    paper: {
                        sx: {
                            minWidth: "128px",
                            borderRadius: "6px",
                            boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
                            backgroundColor: "var(--tb-popover, #ffffff)",
                            color: "var(--tb-popover-foreground, #000000)",
                        },
                    },
                }}
                {...(props as any)}
            />
        );
    }
);
DropdownMenuContent.displayName = "DropdownMenuContent";

// DropdownMenuItem
const DropdownMenuItem = React.forwardRef<HTMLLIElement, MuiMenuItemProps & { inset?: boolean }>(
    ({ className, inset, onClick, ...props }, ref) => {
        const { setOpen } = React.useContext(DropdownMenuContext);

        return (
            <MuiMenuItem
                ref={ref}
                onClick={(e) => {
                    setOpen(false);
                    onClick?.(e as any);
                }}
                className={cn(
                    "relative flex cursor-default select-none items-center gap-2 rounded-sm px-2 py-1.5 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground",
                    inset && "pl-8",
                    className
                )}
                sx={{
                    fontSize: "0.875rem",
                    padding: "6px 12px",
                    "&:hover": {
                        backgroundColor: "var(--tb-accent, #f5f5f5)",
                    },
                    "&:focus": {
                        backgroundColor: "var(--tb-accent, #f5f5f5)",
                    },
                    "& svg": {
                        pointerEvents: "none",
                        fontSize: "16px",
                        flexShrink: 0,
                    },
                }}
                {...(props as any)}
            />
        );
    }
);
DropdownMenuItem.displayName = "DropdownMenuItem";

// DropdownMenuCheckboxItem
const DropdownMenuCheckboxItem = React.forwardRef<
    HTMLLIElement,
    MuiMenuItemProps & { checked?: boolean }
>(({ className, children, checked, onClick, ...props }, ref) => {
    const { setOpen } = React.useContext(DropdownMenuContext);

    return (
        <MuiMenuItem
            ref={ref}
            onClick={(e) => {
                setOpen(false);
                onClick?.(e as any);
            }}
            className={cn(
                "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground",
                className
            )}
            sx={{
                fontSize: "0.875rem",
                padding: "6px 12px",
            }}
            {...(props as any)}
        >
            <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                {checked && <Check className="h-4 w-4" />}
            </span>
            {children}
        </MuiMenuItem>
    );
});
DropdownMenuCheckboxItem.displayName = "DropdownMenuCheckboxItem";

// DropdownMenuRadioItem
const DropdownMenuRadioItem = React.forwardRef<HTMLLIElement, MuiMenuItemProps>(
    ({ className, children, onClick, ...props }, ref) => {
        const { setOpen } = React.useContext(DropdownMenuContext);

        return (
            <MuiMenuItem
                ref={ref}
                onClick={(e) => {
                    setOpen(false);
                    onClick?.(e as any);
                }}
                className={cn(
                    "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none transition-colors focus:bg-accent focus:text-accent-foreground",
                    className
                )}
                sx={{
                    fontSize: "0.875rem",
                    padding: "6px 12px",
                }}
                {...(props as any)}
            >
                <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
                    <Circle className="h-2 w-2 fill-current" />
                </span>
                {children}
            </MuiMenuItem>
        );
    }
);
DropdownMenuRadioItem.displayName = "DropdownMenuRadioItem";

// DropdownMenuLabel
const DropdownMenuLabel = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { inset?: boolean }>(
    ({ className, inset, ...props }, ref) => (
        <div
            ref={ref}
            className={cn(
                "px-2 py-1.5 text-xs font-semibold text-muted-foreground",
                inset && "pl-8",
                className
            )}
            {...props}
        />
    )
);
DropdownMenuLabel.displayName = "DropdownMenuLabel";

// DropdownMenuSeparator
const DropdownMenuSeparator = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ className, ...props }, ref) => (
        <Divider
            ref={ref as any}
            className={cn("-mx-1 my-1 h-px bg-muted", className)}
            {...(props as any)}
        />
    )
);
DropdownMenuSeparator.displayName = "DropdownMenuSeparator";

// DropdownMenuShortcut
const DropdownMenuShortcut = React.forwardRef<HTMLSpanElement, React.HTMLAttributes<HTMLSpanElement>>(
    ({ className, ...props }, ref) => (
        <span
            ref={ref}
            className={cn("ml-auto text-xs tracking-widest opacity-60", className)}
            {...props}
        />
    )
);
DropdownMenuShortcut.displayName = "DropdownMenuShortcut";

// Unused but exported for compatibility
const DropdownMenuGroup = ({ children }: { children: React.ReactNode }) => <>{children}</>;
const DropdownMenuPortal = ({ children }: { children: React.ReactNode }) => <>{children}</>;
const DropdownMenuSub = ({ children }: { children: React.ReactNode }) => <>{children}</>;
const DropdownMenuSubContent = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ children, ...props }, ref) => <div ref={ref} {...props}>{children}</div>
);
DropdownMenuSubContent.displayName = "DropdownMenuSubContent";
const DropdownMenuSubTrigger = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
    ({ children, ...props }, ref) => (
        <div ref={ref} {...props}>
            {children}
            <ChevronRight className="ml-auto" />
        </div>
    )
);
DropdownMenuSubTrigger.displayName = "DropdownMenuSubTrigger";
const DropdownMenuRadioGroup = ({ children }: { children: React.ReactNode }) => <>{children}</>;

export {
    DropdownMenu,
    DropdownMenuTrigger,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuCheckboxItem,
    DropdownMenuRadioItem,
    DropdownMenuLabel,
    DropdownMenuSeparator,
    DropdownMenuShortcut,
    DropdownMenuGroup,
    DropdownMenuPortal,
    DropdownMenuSub,
    DropdownMenuSubContent,
    DropdownMenuSubTrigger,
    DropdownMenuRadioGroup,
}
