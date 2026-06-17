import { FileText } from "lucide-react";

// Tinted badges for a trade's direction + license type. Extracted from MasterForm.
const DIR_COLORS: Record<string, string> = { PURCHASE: 'var(--tb-brand)', SALE: 'var(--tb-success)', COMMISSION_PURCHASE: 'var(--tb-warning)', COMMISSION_SALE: 'var(--tb-brand)' };
const DIR_SOFT_BG: Record<string, string> = { PURCHASE: 'var(--tb-brand-50)', SALE: 'var(--tb-success-soft)', COMMISSION_PURCHASE: 'var(--tb-warning-soft)', COMMISSION_SALE: 'var(--tb-brand-50)' };
const DIR_LABELS: Record<string, string> = { PURCHASE: 'Purchase', SALE: 'Sale', COMMISSION_PURCHASE: 'Commission Purchase', COMMISSION_SALE: 'Commission Sale' };
const LT_COLORS: Record<string, string> = { DFIA: 'var(--tb-info)', INCENTIVE: 'var(--tb-warning)' };
const LT_SOFT_BG: Record<string, string> = { DFIA: 'var(--tb-info-soft)', INCENTIVE: 'var(--tb-warning-soft)' };
const LT_LABELS: Record<string, string> = { DFIA: 'DFIA License', INCENTIVE: 'Incentive License' };

export default function TradeMetaBadges({ direction, licenseType }: { direction: string; licenseType?: string }) {
    return (
        <div className="flex gap-2">
            <span className="badge flex items-center gap-1" style={{ background: DIR_SOFT_BG[direction], color: DIR_COLORS[direction], fontWeight: '600', fontSize: 12, padding: '5px 10px', borderRadius: 6 }}>
                {DIR_LABELS[direction]}
            </span>
            {licenseType && (
                <span className="badge flex items-center gap-1" style={{ background: LT_SOFT_BG[licenseType], color: LT_COLORS[licenseType], fontWeight: '600', fontSize: 12, padding: '5px 10px', borderRadius: 6 }}>
                    <FileText className="size-4" aria-hidden="true" />
                    {LT_LABELS[licenseType]}
                </span>
            )}
        </div>
    );
}
