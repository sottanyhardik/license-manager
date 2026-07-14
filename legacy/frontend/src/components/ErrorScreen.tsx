import { Link } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";

interface ErrorScreenProps {
    /** Large faded code, e.g. "404" / "500". Optional. */
    code?: string;
    icon: LucideIcon;
    /** Visual tone of the icon chip. */
    tone?: "muted" | "destructive" | "warning" | "primary";
    title: string;
    description: string;
    /** Primary action. */
    action: { to: string; label: string; icon?: LucideIcon };
    /** Optional secondary action rendered to the left of the primary one. */
    secondary?: React.ReactNode;
}

const TONE_CLASSES: Record<NonNullable<ErrorScreenProps["tone"]>, string> = {
    muted: "bg-muted text-muted-foreground border-border",
    destructive: "bg-destructive/10 text-destructive border-destructive/20",
    warning: "bg-warning/10 text-warning border-warning/20",
    primary: "bg-primary/10 text-primary border-primary/15",
};

export default function ErrorScreen({
    code,
    icon: Icon,
    tone = "muted",
    title,
    description,
    action,
    secondary,
}: ErrorScreenProps) {
    const reduce = useReducedMotion();
    const ActionIcon = action.icon;

    return (
        <div className="flex min-h-screen items-center justify-center bg-background px-6">
            <motion.div
                className="w-full max-w-md text-center"
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
            >
                <div
                    className={`mx-auto mb-4 flex size-13 items-center justify-center rounded-2xl border ${TONE_CLASSES[tone]}`}
                >
                    <Icon className="size-6" />
                </div>

                {code && (
                    <div className="mb-1 text-6xl font-bold leading-none tracking-tighter text-border">
                        {code}
                    </div>
                )}

                <h1 className="text-xl font-semibold tracking-tight text-foreground">
                    {title}
                </h1>
                <p className="mx-auto mt-2 mb-7 max-w-sm text-sm leading-relaxed text-muted-foreground">
                    {description}
                </p>

                <div className="flex flex-wrap items-center justify-center gap-2.5">
                    {secondary}
                    <Button asChild>
                        <Link to={action.to}>
                            {ActionIcon && <ActionIcon className="size-4" />}
                            {action.label}
                        </Link>
                    </Button>
                </div>
            </motion.div>
        </div>
    );
}
