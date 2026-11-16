import { useCallback, useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ChevronDownIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface AccordionSection {
    id: string;
    title: string;
    defaultOpen?: boolean;
    render: () => ReactNode;
}

export interface ModuleAccordionProps {
    sections: AccordionSection[];
    /** Persists open state in sessionStorage under this key (per record + tab). */
    persistKey?: string;
    className?: string;
}

const storageKey = (k: string) => `module-accordion:${k}`;

function readOpen(persistKey: string | undefined, sections: AccordionSection[]): string[] {
    const defaults = sections.filter((s) => s.defaultOpen).map((s) => s.id);
    if (!persistKey) return defaults;
    try {
        const raw = sessionStorage.getItem(storageKey(persistKey));
        if (raw) {
            const parsed: unknown = JSON.parse(raw);
            if (Array.isArray(parsed)) return parsed.filter((x): x is string => typeof x === "string");
        }
    } catch {
        /* storage unavailable or corrupt: fall back to defaults */
    }
    return defaults;
}

/** One-level accordion of independent sections. Bodies render only while open. */
export function ModuleAccordion({ sections, persistKey, className }: ModuleAccordionProps) {
    const baseId = useId();
    const [open, setOpen] = useState<string[]>(() => readOpen(persistKey, sections));
    const buttons = useRef<(HTMLButtonElement | null)[]>([]);

    const toggle = useCallback((id: string) => {
        const next = open.includes(id) ? open.filter((x) => x !== id) : [...open, id];
        setOpen(next);
        if (persistKey) {
            try {
                sessionStorage.setItem(storageKey(persistKey), JSON.stringify(next));
            } catch {
                /* ignore */
            }
        }
    }, [open, persistKey]);

    const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>, index: number) => {
        const last = sections.length - 1;
        let target: number | null = null;
        if (e.key === "ArrowDown") target = index === last ? 0 : index + 1;
        else if (e.key === "ArrowUp") target = index === 0 ? last : index - 1;
        else if (e.key === "Home") target = 0;
        else if (e.key === "End") target = last;
        if (target !== null) {
            e.preventDefault();
            buttons.current[target]?.focus();
        }
    };

    return (
        <div className={cn("divide-y divide-border rounded-lg border border-border bg-card", className)}>
            {sections.map((s, i) => {
                const isOpen = open.includes(s.id);
                const panelId = `${baseId}-${s.id}-panel`;
                const headerId = `${baseId}-${s.id}-header`;
                return (
                    <section key={s.id}>
                        <h3>
                            <button
                                ref={(el) => { buttons.current[i] = el; }}
                                id={headerId}
                                type="button"
                                aria-expanded={isOpen}
                                aria-controls={panelId}
                                onClick={() => toggle(s.id)}
                                onKeyDown={(e) => onKeyDown(e, i)}
                                className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left text-sm font-medium cursor-pointer hover:bg-muted/50 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
                            >
                                {s.title}
                                <ChevronDownIcon aria-hidden="true" className={cn("size-4 shrink-0 text-muted-foreground transition-transform motion-reduce:transition-none", isOpen && "rotate-180")} />
                            </button>
                        </h3>
                        <div id={panelId} role="region" aria-labelledby={headerId} hidden={!isOpen} className="px-4 pb-4">
                            {isOpen ? s.render() : null}
                        </div>
                    </section>
                );
            })}
        </div>
    );
}
