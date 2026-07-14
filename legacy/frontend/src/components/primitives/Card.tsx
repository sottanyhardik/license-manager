import React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, style, children }: { className?: string; style?: React.CSSProperties; children: React.ReactNode }) {
    return <div className={cn("surface-card", className)} style={style}>{children}</div>;
}
export function CardHeader({ className, style, children }: { className?: string; style?: React.CSSProperties; children: React.ReactNode }) {
    return <div className={cn("card-header", className)} style={style}>{children}</div>;
}
export function CardBody({ className, style, children }: { className?: string; style?: React.CSSProperties; children: React.ReactNode }) {
    return <div className={cn("card-body", className)} style={style}>{children}</div>;
}
export function CardFooter({ className, style, children }: { className?: string; style?: React.CSSProperties; children: React.ReactNode }) {
    return <div className={cn("px-5 py-3 border-t border-border/60", className)} style={style}>{children}</div>;
}
export default Card;
