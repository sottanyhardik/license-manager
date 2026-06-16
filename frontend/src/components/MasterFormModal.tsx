import { X, Pencil, Copy } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import MasterForm from "../pages/masters/MasterForm";

export default function MasterFormModal({ show, onHide, entityName, recordId, mode = "edit", onSuccess }) {
    if (!show) return null;

    const modeLabel = mode === "copy" ? "Copy" : "Edit";
    const ModeIcon = mode === "copy" ? Copy : Pencil;
    const entityTitle = entityName === "allotments" ? "Allotment" : entityName;

    return (
        <Dialog open={show} onOpenChange={(o) => !o && onHide()}>
            <DialogContent className="h-[95vh] w-[95vw] max-w-5xl overflow-hidden p-0">
                <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: "linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))" }}>
                    <h5 className="flex items-center gap-2 text-[1.1rem] font-semibold tracking-tight text-white">
                        <ModeIcon className="size-5" />
                        {modeLabel} {entityTitle}
                    </h5>
                    <button type="button" onClick={onHide} aria-label="Close" className="flex size-8 cursor-pointer items-center justify-center rounded-sm border-0 bg-transparent text-white opacity-70 hover:opacity-100">
                        <X className="size-4" />
                    </button>
                </div>
                <div className="overflow-auto bg-muted/40" style={{ height: "calc(95vh - 68px)" }}>
                    <MasterForm entityName={entityName} recordId={recordId} isModal onClose={onHide} onSuccess={onSuccess} />
                </div>
            </DialogContent>
        </Dialog>
    );
}
