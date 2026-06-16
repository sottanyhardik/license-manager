import { X, FileText } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";

import BOETransferLetter from "../pages/BOETransferLetter";
import AllotmentAction from "../pages/AllotmentAction";
import TradeTransferLetter from "../pages/TradeTransferLetter";

export default function TransferLetterModal({ show, onHide, type, entityId }) {
    if (!show || !entityId) return null;

    return (
        <Dialog open={show} onOpenChange={(o) => !o && onHide()}>
            <DialogContent className="h-[95vh] w-[95vw] max-w-6xl overflow-hidden p-0">
                {/* Header */}
                <div className="flex items-center justify-between px-6 py-4 text-white" style={{ background: "linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))" }}>
                    <h5 className="flex items-center gap-2 text-[1.1rem] font-semibold tracking-tight text-white">
                        <FileText className="size-5" />
                        Generate Transfer Letter
                    </h5>
                    <button type="button" onClick={onHide} aria-label="Close" className="flex size-8 cursor-pointer items-center justify-center rounded-sm border-0 bg-transparent text-white opacity-70 hover:opacity-100">
                        <X className="size-4" />
                    </button>
                </div>
                {/* Body — full-height scroll */}
                <div className="overflow-auto bg-muted/40" style={{ height: "calc(95vh - 68px)" }}>
                    {type === "boe" ? (
                        <BOETransferLetter boeId={entityId} isModal onClose={onHide} />
                    ) : type === "trade" ? (
                        <TradeTransferLetter tradeId={entityId} isModal onClose={onHide} />
                    ) : (
                        <AllotmentAction allotmentId={entityId} isModal onClose={onHide} />
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}
