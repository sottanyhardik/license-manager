import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle,
} from "@/components/ui/dialog";

export interface ConfirmOptions {
    title: string;
    description?: ReactNode;
    confirmLabel?: string;
    cancelLabel?: string;
    tone?: "default" | "danger";
    /** Type-to-confirm text for destructive bulk operations. */
    requireText?: string;
}

export interface ConfirmDialogProps extends ConfirmOptions {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onConfirm: () => void | Promise<void>;
}

/** Controlled confirm dialog (Radix Dialog as alertdialog). Esc / overlay = cancel. */
export function ConfirmDialog({
    open, onOpenChange, onConfirm, title, description,
    confirmLabel = "Confirm", cancelLabel = "Cancel", tone = "default", requireText,
}: ConfirmDialogProps) {
    const [pending, setPending] = useState(false);
    const [typed, setTyped] = useState("");
    const cancelRef = useRef<HTMLButtonElement>(null);
    const confirmRef = useRef<HTMLButtonElement>(null);
    const gated = !!requireText && typed !== requireText;

    const handleConfirm = async () => {
        setPending(true);
        try {
            await onConfirm();
            onOpenChange(false);
        } finally {
            setPending(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={(o) => { if (pending && !o) return; if (!o) setTyped(""); onOpenChange(o); }}>
            <DialogContent
                role="alertdialog"
                showCloseButton={false}
                {...(description ? {} : { "aria-describedby": undefined })}
                className="max-w-md"
                onOpenAutoFocus={(e) => {
                    e.preventDefault();
                    (tone === "danger" || requireText ? cancelRef : confirmRef).current?.focus();
                }}
            >
                <DialogHeader>
                    <DialogTitle>{title}</DialogTitle>
                    {description ? <DialogDescription asChild><div>{description}</div></DialogDescription> : null}
                </DialogHeader>
                {requireText && (
                    <label className="grid gap-1 text-sm">
                        <span>Type <strong>{requireText}</strong> to confirm</span>
                        <Input value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
                    </label>
                )}
                <DialogFooter>
                    <Button ref={cancelRef} type="button" variant="outline" disabled={pending} onClick={() => onOpenChange(false)}>
                        {cancelLabel}
                    </Button>
                    <Button
                        ref={confirmRef}
                        type="button"
                        variant={tone === "danger" ? "destructive" : "default"}
                        disabled={pending || gated}
                        aria-busy={pending || undefined}
                        onClick={handleConfirm}
                    >
                        {confirmLabel}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

type ConfirmFn = (opts: ConfirmOptions) => Promise<boolean>;
const ConfirmContext = createContext<ConfirmFn | null>(null);

/** Mount once near the app root to enable `useConfirm`. */
export function ConfirmProvider({ children }: { children: ReactNode }) {
    const [state, setState] = useState<{ opts: ConfirmOptions; resolve: (v: boolean) => void } | null>(null);
    const [open, setOpen] = useState(false);

    const confirm = useCallback<ConfirmFn>((opts) => new Promise<boolean>((resolve) => {
        setState({ opts, resolve });
        setOpen(true);
    }), []);

    const settle = (value: boolean) => {
        state?.resolve(value);
        setOpen(false);
    };

    return (
        <ConfirmContext.Provider value={confirm}>
            {children}
            {state && (
                <ConfirmDialog
                    {...state.opts}
                    open={open}
                    onOpenChange={(o) => { if (!o) settle(false); }}
                    onConfirm={() => { state.resolve(true); }}
                />
            )}
        </ConfirmContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useConfirm(): ConfirmFn {
    const ctx = useContext(ConfirmContext);
    if (!ctx) throw new Error("useConfirm requires <ConfirmProvider>");
    return ctx;
}

/** Non-throwing variant for components that only sometimes need confirmation. */
// eslint-disable-next-line react-refresh/only-export-components
export function useOptionalConfirm(): ConfirmFn | null {
    return useContext(ConfirmContext);
}
