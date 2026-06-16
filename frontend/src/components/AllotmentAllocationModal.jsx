import { X, PackageOpen } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import AllotmentAction from "../pages/AllotmentAction";

export default function AllotmentAllocationModal({ show, onHide, allotmentId }) {
    if (!show || !allotmentId) return null;

    return (
        <Dialog open={show} onOpenChange={(o) => !o && onHide()}>
            <DialogContent className="h-[95vh] w-[95vw] max-w-7xl overflow-hidden p-0">
                <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: "linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))" }}>
                    <h5 className="flex items-center gap-2 text-[1.1rem] font-semibold tracking-tight text-white">
                        <PackageOpen className="size-5" />
                        Allotment Allocation
                    </h5>
                    <button type="button" onClick={onHide} aria-label="Close" className="flex size-8 cursor-pointer items-center justify-center rounded-sm border-0 bg-transparent text-white opacity-70 hover:opacity-100">
                        <X className="size-4" />
                    </button>
                </div>
                <div className="overflow-auto bg-muted/40" style={{ height: "calc(95vh - 68px)" }}>
                    <AllotmentAction allotmentId={allotmentId} isModal onClose={onHide} />
                </div>
            </DialogContent>
        </Dialog>
    );
}
