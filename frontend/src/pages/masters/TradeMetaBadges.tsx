import { FileText } from "lucide-react";

// Tinted badges for a trade's direction + license type. Extracted from MasterForm.
const DIR_COLORS: Record<string, string> = { PURCHASE: 'var(--tb-brand)', SALE: 'var(--tb-success)', COMMISSION_PURCHASE: 'var(--tb-warning)', COMMISSION_SALE: 'var(--tb-brand)' };
const DIR_SOFT_BG: Record<string, string> = { PURCHASE: 'var(--tb-brand-50)', SALE: 'var(--tb-success-soft)', COMMISSION_PURCHASE: 'var(--tb-warning-soft)', COMMISSION_SALE: 'var(--tb-brand-50)' };
const DIR_LABELS: Record<string, string> = { PURCHASE: 'Purchase', SALE: 'Sale', COMMISSION_PURCHASE: 'Commission Purchase', COMMISSION_SALE: 'Commission Sale' };
const LT_COLORS: Record<string, string> = { DFIA: 'var(--tb-info)', INCENTIVE: 'var(--tb-warning)' };
const LT_SOFT_BG: Record<string, string> = { DFIA: 'var(--tb-info-soft)', INCENTIVE: 'var(--tb-warning-soft)' };
const LT_LABELS: Record<string, string> = { DFIA: 'DFIA License', INCENTIVE: 'Incentive License' };

export default function TradeMetaBadges({ direction, licenseType }: { direction: string; licenseType?: string }) {
    const directionLabel = DIR_LABELS[direction] || direction;
    const licenseLabel = licenseType ? (LT_LABELS[licenseType] || licenseType) : undefined;
    return (
        <div className="flex flex-wrap gap-1.5" aria-label={`Trade: ${directionLabel}${licenseLabel ? `; ${licenseLabel}` : ''}`}>
            <span className="inline-flex min-h-6 items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold" style={{ background: DIR_SOFT_BG[direction] || 'var(--tb-muted)', color: DIR_COLORS[direction] || 'var(--tb-text-secondary)' }}>
                {directionLabel}
            </span>
            {licenseType && (
                <span className="inline-flex min-h-6 items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold" style={{ background: LT_SOFT_BG[licenseType] || 'var(--tb-muted)', color: LT_COLORS[licenseType] || 'var(--tb-text-secondary)' }}>
                    <FileText className="size-4" aria-hidden="true" />
                    {licenseLabel}
                </span>
            )}
        </div>
    );
}
