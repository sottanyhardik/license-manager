import { useContext, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Layers3, Loader2 } from "lucide-react";

import api from "@/api/axios";
import { AuthContext } from "@/context/AuthContext";
import { Card, CardContent } from "@/components/ui/card";

import { extractApiError } from "./licenseOverviewHelpers";
import { licenseOverviewKeys } from "./useLicenseOverviewSummary";
import { licenseSionNormKeys, useLicenseSionNorm } from "./useLicenseSionNorm";
import InlineNormEditor from "./InlineNormEditor";

interface SionNormCardProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

/**
 * Card below the header showing the license's SION Norm — sourced from
 * `export_license[0].norm_class` (there is no dedicated "SION Norm" field or
 * endpoint; see `useLicenseSionNorm`'s doc comment). Owns its own
 * editing/selection/saving state and performs the safe-write PATCH itself.
 */
export default function SionNormCard({ licenseId, isActive }: SionNormCardProps) {
    const { hasRole } = useContext(AuthContext);
    const queryClient = useQueryClient();

    const { exportRows, primaryRow, isLoading } = useLicenseSionNorm(licenseId, isActive);

    const [isEditing, setIsEditing] = useState(false);
    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [saving, setSaving] = useState(false);

    if (!isActive) return null;

    const currentNorm = primaryRow?.norm_class_detail ?? null;
    // Gate on role AND on there being an export row to attach a norm to —
    // creating one is out of scope, so with zero rows the edit affordance
    // must not appear at all.
    const canEdit = hasRole("LICENSE_MANAGER") && !!primaryRow;

    const handleEditStart = () => {
        setSelectedId(currentNorm?.id ?? null);
        setIsEditing(true);
    };

    const handleCancel = () => {
        setIsEditing(false);
        setSelectedId(null);
    };

    const handleSave = async () => {
        if (!licenseId || !primaryRow || selectedId == null) return;
        setSaving(true);
        try {
            // Safe-write trick: send every export row's id (so
            // `LicenseWriteMixin.update` doesn't delete sibling rows as
            // "missing from the payload"), only adding `norm_class` to the
            // one row actually being edited.
            await api.patch(`licenses/${licenseId}/`, {
                export_license: exportRows.map((row) =>
                    row.id === primaryRow.id ? { id: row.id, norm_class: selectedId } : { id: row.id }
                ),
            });
            toast.success("SION norm updated");
            queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.summary(licenseId) });
            queryClient.invalidateQueries({ queryKey: licenseOverviewKeys.planning(licenseId) });
            queryClient.invalidateQueries({ queryKey: licenseSionNormKeys.detail(licenseId) });
            setIsEditing(false);
            setSelectedId(null);
        } catch (err) {
            toast.error(extractApiError(err, "Failed to update SION norm"));
            // Keep the editor open so the user can retry.
        } finally {
            setSaving(false);
        }
    };

    return (
        <Card className="border-border/70 shadow-sm">
            <CardContent className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <div className="flex min-w-0 items-center gap-2.5">
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-md border border-primary/15 bg-primary/10 text-primary">
                        <Layers3 className="size-4" aria-hidden="true" />
                    </span>
                    <div className="min-w-0">
                        <div className="text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
                            SION Norm
                        </div>
                        <div className="mt-0.5 text-base font-semibold text-foreground">
                            {isLoading ? (
                                <Loader2 className="size-4 animate-spin text-muted-foreground" aria-hidden="true" />
                            ) : (
                                currentNorm?.norm_class ?? "—"
                            )}
                        </div>
                    </div>
                </div>

                <InlineNormEditor
                    isEditing={isEditing}
                    selectedId={selectedId}
                    onSelectedIdChange={setSelectedId}
                    onEditStart={handleEditStart}
                    onSave={handleSave}
                    onCancel={handleCancel}
                    saving={saving}
                    canEdit={canEdit}
                />

                {currentNorm && (
                    <div className="min-w-0 text-right">
                        <div className="text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
                            Description
                        </div>
                        <div className="mt-0.5 truncate text-sm font-medium text-foreground">
                            {currentNorm.description || "—"}
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
