import { useEffect, useRef, useState } from "react";
import { SearchIcon, XIcon } from "lucide-react";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

export interface SearchInputProps {
    value: string;
    onChange: (debounced: string) => void;
    label: string;
    placeholder?: string;
    /** Debounce in ms (default 300). */
    delay?: number;
    size?: "sm" | "default";
    className?: string;
}

export function SearchInput({ value, onChange, label, placeholder, delay = 300, size = "default", className }: SearchInputProps) {
    const [draft, setDraft] = useState(value);
    const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const lastEmitted = useRef(value);

    // Sync external value changes.
    useEffect(() => {
        if (value !== lastEmitted.current) {
            lastEmitted.current = value;
            setDraft(value);
        }
    }, [value]);

    useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);

    const emit = (next: string) => {
        lastEmitted.current = next;
        onChange(next);
    };

    const schedule = (next: string) => {
        setDraft(next);
        if (timer.current) clearTimeout(timer.current);
        timer.current = setTimeout(() => emit(next), delay);
    };

    const clear = () => {
        if (timer.current) clearTimeout(timer.current);
        setDraft("");
        emit("");
    };

    return (
        <div className={cn("relative", className)}>
            <SearchIcon aria-hidden="true" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
                type="search"
                aria-label={label}
                placeholder={placeholder}
                value={draft}
                onChange={(e) => schedule(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Escape" && draft) { e.preventDefault(); clear(); } }}
                className={cn("pl-8 pr-8 [&::-webkit-search-cancel-button]:hidden", size === "sm" && "h-8 text-xs")}
            />
            {draft && (
                <button
                    type="button"
                    aria-label="Clear search"
                    onClick={clear}
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded-sm text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 cursor-pointer"
                >
                    <XIcon className="size-4" aria-hidden="true" />
                </button>
            )}
        </div>
    );
}
