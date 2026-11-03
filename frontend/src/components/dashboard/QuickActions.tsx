import { Link } from "react-router-dom";
import { FileSpreadsheet, FileText, GitCompareArrows, Network, Plus, ReceiptText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { QUICK_ACTION_PATHS } from "./dashboardLinks";

export type QuickActionPermissions = {
    newLicence: boolean;
    newAllotment: boolean;
    newBoe: boolean;
    newInvoice: boolean;
    reconciliation: boolean;
    reports: boolean;
};

const ACTIONS = [
    { key: "newLicence", label: "New Licence", path: QUICK_ACTION_PATHS.newLicence, icon: Plus },
    { key: "newAllotment", label: "New Allotment", path: QUICK_ACTION_PATHS.newAllotment, icon: Network },
    { key: "newBoe", label: "New BOE", path: QUICK_ACTION_PATHS.newBoe, icon: ReceiptText },
    { key: "newInvoice", label: "New Invoice", path: QUICK_ACTION_PATHS.newInvoice, icon: FileText },
    { key: "reconciliation", label: "Reconciliation", path: QUICK_ACTION_PATHS.reconciliation, icon: GitCompareArrows },
    { key: "reports", label: "View Reports", path: QUICK_ACTION_PATHS.reports, icon: FileSpreadsheet },
] as const;

/** Each action is shown only when the caller's roles match its route guard. */
export default function QuickActions({ permissions }: { permissions: QuickActionPermissions }) {
    const visible = ACTIONS.filter((action) => permissions[action.key]);
    if (visible.length === 0) return null;

    return (
        <nav aria-label="Quick actions" className="flex flex-wrap items-center gap-2">
            {visible.map((action) => {
                const Icon = action.icon;
                return (
                    <Button key={action.key} asChild variant="secondary" size="sm">
                        <Link to={action.path}>
                            <Icon className="size-4" aria-hidden="true" />
                            {action.label}
                        </Link>
                    </Button>
                );
            })}
        </nav>
    );
}
