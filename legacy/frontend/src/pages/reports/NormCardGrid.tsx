import { Inbox, Loader2, RefreshCw, Tag } from "lucide-react";

interface NormCardGridProps {
    availableNorms: any[];
    activeNormTab: string | null;
    setActiveNormTab: (n: any) => void;
    setReportData: (d: any) => void;
    loading: boolean;
}

/** "Available Norms" selector grid — extracted verbatim from ItemPivotReport. */
export default function NormCardGrid({ availableNorms, activeNormTab, setActiveNormTab, setReportData, loading }: NormCardGridProps) {
    return (
            <div className="mb-6 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                {/* Header */}
                <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
                    <div className="flex items-center gap-2">
                        <Tag className="size-4" style={{ color: 'var(--tb-brand)' }} aria-hidden="true" />
                        <span className="text-sm font-bold tracking-tight text-foreground">Available Norms</span>
                        {availableNorms.length > 0 && (
                            <span className="rounded-full px-2 py-0.5 text-[10px] font-bold" style={{ background: 'var(--tb-brand-50)', color: 'var(--tb-brand)' }}>
                                {availableNorms.length}
                            </span>
                        )}
                    </div>
                    <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                        <RefreshCw className="size-3" />E1, E5, E126, E132 are conversion norms
                    </span>
                </div>

                {/* Norm grid */}
                <div className="p-4">
                    {availableNorms.length > 0 ? (
                        <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))' }}>
                            {availableNorms.map((normObj) => {
                                const normClass = normObj.norm_class || normObj;
                                // Never render a blank norm card (guards against malformed/empty entries).
                                if (!normClass) return null;
                                const description = normObj.description || '';
                                const isConversionNorm = ['E1', 'E5', 'E126', 'E132'].includes(normClass);
                                const isActive = activeNormTab === normClass;
                                const activeBg = isConversionNorm ? 'var(--tb-success)' : 'var(--tb-brand)';
                                const softBg = isConversionNorm ? 'var(--tb-success-soft)' : 'var(--tb-brand-50)';
                                const softText = isConversionNorm ? 'var(--tb-success-text)' : 'var(--tb-brand)';
                                const softBorder = isConversionNorm ? 'var(--tb-success-border, #B7E2BE)' : 'var(--tb-brand-100)';
                                return (
                                    <button
                                        key={normClass}
                                        type="button"
                                        onClick={() => {
                                            if (activeNormTab !== normClass) setReportData(null);
                                            setActiveNormTab(normClass);
                                        }}
                                        style={{
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'flex-start',
                                            padding: '10px 14px',
                                            borderRadius: 8,
                                            border: isActive ? `2px solid ${activeBg}` : `1px solid ${softBorder}`,
                                            // activeBg is a CSS var() — the old `${activeBg}dd` hex-alpha trick produced
                                            // invalid CSS (`var(--tb-success)dd`), which killed the background and left
                                            // white text on a white card. Solid var() fill is always valid + readable.
                                            background: isActive ? activeBg : softBg,
                                            color: isActive ? '#fff' : softText,
                                            cursor: 'pointer',
                                            transition: 'all 0.18s ease',
                                            boxShadow: isActive ? `0 4px 12px ${isConversionNorm ? 'rgba(40,167,69,.25)' : 'rgba(59,130,246,.25)'}` : 'none',
                                            textAlign: 'left',
                                        }}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, width: '100%' }}>
                                            <span style={{
                                                fontSize: 18, fontWeight: '800', letterSpacing: '-0.5px', lineHeight: 1,
                                                color: isActive ? '#fff' : softText,
                                            }}>{normClass}</span>
                                            {loading && isActive && (
                                                <Loader2 className="size-3.5 animate-spin ml-auto" style={{ color: '#fff' }} />
                                            )}
                                            {isConversionNorm && !isActive && (
                                                <RefreshCw className="ml-auto size-3" style={{ color: softText, opacity: 0.6 }} />
                                            )}
                                        </div>
                                        {description && (
                                            <span style={{
                                                fontSize: 10.5, lineHeight: '1.3', marginTop: 3,
                                                color: isActive ? 'rgba(255,255,255,0.85)' : 'var(--tb-text-secondary)',
                                                overflow: 'hidden', display: '-webkit-box',
                                                WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                                                maxWidth: '100%',
                                            }}>{description}</span>
                                        )}
                                    </button>
                                );
                            })}
                        </div>
                    ) : (
                        <div className="flex flex-col items-center py-6 text-center text-muted-foreground">
                            <Inbox className="mb-2 size-8 opacity-30" />
                            <p className="text-sm">No norms available. Try adjusting the filters.</p>
                        </div>
                    )}
                </div>
            </div>
    );
}
