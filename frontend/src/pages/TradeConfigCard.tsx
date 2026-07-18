import { Award, FileText, Link, SlidersHorizontal } from "lucide-react";

interface TradeConfigCardProps {
    formData: any;
    setFormData: (updater: any) => void;
    id?: string;
    autoCreatePaired: boolean;
    setAutoCreatePaired: (v: boolean) => void;
    directionMeta: Record<string, { label: string; icon: any; color: string; soft: string }>;
}

/** Transaction-type + license-type selectors and the auto-create-paired toggle.
 *  Extracted verbatim from TradeForm (state passed through as props). */
export default function TradeConfigCard({ formData, setFormData, id, autoCreatePaired, setAutoCreatePaired, directionMeta }: TradeConfigCardProps) {
    return (
                <div className="rounded-xl border border-border bg-card mb-3">
                    <div className="flex items-center gap-2 border-b border-border px-4 py-3 rounded-t-[12px]">
                        <h6 className="font-semibold m-0">
                            <SlidersHorizontal className="size-4" aria-hidden="true" />
                            Trade Configuration
                        </h6>
                    </div>
                    <div className="p-4">
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                            <div>
                                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                    TRANSACTION TYPE <span className="text-destructive">*</span>
                                </label>
                                <div className="flex gap-2 flex-wrap">
                                    {Object.entries(directionMeta).map(([val, m]) => {
                                        const Icon = m.icon;
                                        const active = formData.direction === val;
                                        return (
                                            <button key={val} type="button"
                                                onClick={() => setFormData(prev => ({ ...prev, direction: val }))}
                                                className="inline-flex items-center gap-1.5"
                                                style={{
                                                    border: `2px solid ${active ? m.color : 'var(--tb-border-soft)'}`,
                                                    background: active ? m.soft : 'var(--tb-card-bg)',
                                                    color: active ? m.color : 'var(--tb-text-secondary)',
                                                    borderRadius: 'var(--tb-r-md)', padding: '8px 14px',
                                                    fontWeight: active ? '600' : '500',
                                                    fontSize: '0.83rem', cursor: 'pointer', transition: 'all 0.15s',
                                                }}>
                                                <Icon className="size-3.5" aria-hidden="true" />{m.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                            <div>
                                <label className="mb-2 block text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                                    LICENSE TYPE <span className="text-destructive">*</span>
                                </label>
                                <div className="flex gap-2">
                                    {[{ val:'DFIA', label:'DFIA License', icon: FileText, color:'var(--tb-brand)', soft:'var(--tb-brand-50)' },
                                      { val:'INCENTIVE', label:'Incentive License', icon: Award, color:'var(--tb-warning)', soft:'var(--tb-warning-soft)' }].map(m => {
                                        const Icon = m.icon;
                                        const active = formData.license_type === m.val;
                                        return (
                                            <button key={m.val} type="button"
                                                onClick={() => setFormData(prev => ({ ...prev, license_type: m.val, incentive_license: m.val === 'DFIA' ? null : prev.incentive_license }))}
                                                className="inline-flex items-center gap-1.5"
                                                style={{
                                                    border: `2px solid ${active ? m.color : 'var(--tb-border-soft)'}`,
                                                    background: active ? m.soft : 'var(--tb-card-bg)',
                                                    color: active ? m.color : 'var(--tb-text-secondary)',
                                                    borderRadius: 'var(--tb-r-md)', padding: '8px 16px',
                                                    fontWeight: active ? '600' : '500',
                                                    fontSize: '0.83rem', cursor: 'pointer', transition: 'all 0.15s',
                                                }}>
                                                <Icon className="size-3.5" aria-hidden="true" />{m.label}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                        {!id && ['PURCHASE', 'SALE'].includes(formData.direction) && (
                            <div className="flex items-center gap-2 mt-3 p-2 rounded bg-info/10 border border-info/30">
                                <input
                                    type="checkbox"
                                    id="autoCreatePaired"
                                    checked={autoCreatePaired}
                                    onChange={e => setAutoCreatePaired(e.target.checked)}
                                    className="cursor-pointer"
                                />
                                <label htmlFor="autoCreatePaired" className="cursor-pointer text-sm text-info mb-0 flex items-center gap-1.5">
                                    <Link className="size-4" aria-hidden="true" />
                                    Auto-create linked {formData.direction === 'PURCHASE' ? 'Sale' : 'Purchase'} trade with same lines
                                </label>
                            </div>
                        )}
                    </div>
                </div>
    );
}
