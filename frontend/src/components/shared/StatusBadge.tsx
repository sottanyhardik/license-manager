import type { LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { TONE_MAP, type Tone } from "./tone";

export interface StatusBadgeProps {
    tone: Tone;
    label: string;
    appearance?: "soft" | "solid" | "outline";
    icon?: LucideIcon;
    title?: string;
    className?: string;
}

/** Tone-driven status badge. The text label is always rendered. */
export function StatusBadge({ tone, label, appearance = "soft", icon: Icon, title, className }: StatusBadgeProps) {
    return (
        <Badge
            title={title}
            data-tone={tone}
            className={cn(TONE_MAP[tone][appearance], className)}
        >
            {Icon && <Icon aria-hidden="true" />}
            {label}
        </Badge>
    );
}
