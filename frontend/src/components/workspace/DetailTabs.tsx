import { useState, type ReactNode } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export interface DetailTab {
    id: string;
    label: string;
    /** false hides the tab entirely (e.g. role/feature gating). */
    visible?: boolean;
    /** Lazy: called only while the tab is active. */
    render: () => ReactNode;
}

export interface DetailTabsProps {
    /** e.g. `license:${id}`. Changing it unmounts all tab content and resets the active tab. */
    recordKey: string;
    tabs: DetailTab[];
    value?: string;
    onValueChange?: (id: string) => void;
    className?: string;
    /** Accessible name for the tablist, e.g. "License 0310... sections". */
    ariaLabel?: string;
}

function DetailTabsInner({ tabs, value, onValueChange, className, ariaLabel }: Omit<DetailTabsProps, "recordKey">) {
    const shown = tabs.filter((t) => t.visible !== false);
    const [internal, setInternal] = useState(shown[0]?.id ?? "");
    const requested = value ?? internal;
    // Unknown / hidden -> first visible.
    const active = shown.some((t) => t.id === requested) ? requested : (shown[0]?.id ?? "");

    if (shown.length === 0) return null;

    return (
        <Tabs
            value={active}
            onValueChange={(id) => { setInternal(id); onValueChange?.(id); }}
            className={className}
        >
            <TabsList aria-label={ariaLabel} className="h-auto max-w-full flex-wrap justify-start">
                {shown.map((t) => (
                    <TabsTrigger key={t.id} value={t.id}>{t.label}</TabsTrigger>
                ))}
            </TabsList>
            {shown.map((t) => (
                <TabsContent key={t.id} value={t.id} className="mt-3">
                    {t.id === active ? t.render() : null}
                </TabsContent>
            ))}
        </Tabs>
    );
}

/** Record-level tabs. Only the active tab body mounts; switching records remounts everything. */
export function DetailTabs({ recordKey, ...rest }: DetailTabsProps) {
    return <DetailTabsInner key={recordKey} {...rest} />;
}
