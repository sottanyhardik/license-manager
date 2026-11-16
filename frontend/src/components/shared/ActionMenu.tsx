import { useContext } from "react";
import { Link } from "react-router-dom";
import { EllipsisVerticalIcon, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { AuthContext } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { useOptionalConfirm, type ConfirmOptions } from "./ConfirmDialog";

export interface ActionMenuItem {
    id: string;
    label: string;
    icon?: LucideIcon;
    onSelect?: () => void;
    to?: string;
    tone?: "default" | "danger";
    disabled?: boolean;
    /** Shown as a tooltip (title) and linked via aria-describedby when disabled. */
    disabledReason?: string;
    /** UI hint only; the backend remains authoritative. */
    anyRole?: string[];
    /** Routed through useConfirm before onSelect. */
    confirm?: ConfirmOptions;
    separatorBefore?: boolean;
}

export interface ActionMenuProps {
    items: ActionMenuItem[];
    /** aria-label of the trigger, e.g. "Actions for BOE 1234". */
    label: string;
    trigger?: "icon" | "button";
}

export function ActionMenu({ items, label, trigger = "icon" }: ActionMenuProps) {
    const { hasAnyRole } = useContext(AuthContext);
    const confirm = useOptionalConfirm();

    const visible = items.filter((i) => !i.anyRole || hasAnyRole(i.anyRole));
    if (visible.length === 0) return null;

    const select = async (item: ActionMenuItem) => {
        if (item.confirm) {
            if (!confirm) throw new Error("ActionMenu item.confirm requires <ConfirmProvider>");
            if (!(await confirm(item.confirm))) return;
        }
        item.onSelect?.();
    };

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                {trigger === "icon" ? (
                    <Button type="button" variant="ghost" size="icon" aria-label={label}>
                        <EllipsisVerticalIcon aria-hidden="true" />
                    </Button>
                ) : (
                    <Button type="button" variant="outline" aria-label={label}>
                        Actions
                    </Button>
                )}
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
                {visible.map((item) => {
                    const Icon = item.icon;
                    const descId = item.disabled && item.disabledReason ? `${item.id}-reason` : undefined;
                    const body = (
                        <>
                            {Icon && <Icon aria-hidden="true" />}
                            {item.label}
                            {descId && <span id={descId} className="sr-only">{item.disabledReason}</span>}
                        </>
                    );
                    const cls = cn(item.tone === "danger" && "text-destructive focus:text-destructive");
                    return (
                        <div key={item.id}>
                            {item.separatorBefore && <DropdownMenuSeparator />}
                            {item.to && !item.disabled ? (
                                <DropdownMenuItem asChild className={cls}><Link to={item.to}>{body}</Link></DropdownMenuItem>
                            ) : (
                                <DropdownMenuItem
                                    disabled={item.disabled}
                                    title={item.disabled ? item.disabledReason : undefined}
                                    aria-describedby={descId}
                                    className={cls}
                                    onSelect={() => { void select(item); }}
                                >
                                    {body}
                                </DropdownMenuItem>
                            )}
                        </div>
                    );
                })}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
