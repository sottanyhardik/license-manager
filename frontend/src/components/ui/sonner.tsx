import { useEffect, useState } from "react";
import { Toaster as Sonner, type ToasterProps } from "sonner";

/**
 * Sonner toaster wired to the app's [data-theme] dark-mode attribute.
 */
const Toaster = ({ ...props }: ToasterProps) => {
    const [theme, setTheme] = useState<"light" | "dark">(() =>
        document.documentElement.getAttribute("data-theme") === "dark"
            ? "dark"
            : "light"
    );

    useEffect(() => {
        const observer = new MutationObserver(() => {
            setTheme(
                document.documentElement.getAttribute("data-theme") === "dark"
                    ? "dark"
                    : "light"
            );
        });
        observer.observe(document.documentElement, {
            attributes: true,
            attributeFilter: ["data-theme"],
        });
        return () => observer.disconnect();
    }, []);

    return (
        <Sonner
            theme={theme}
            className="toaster group"
            position="top-right"
            richColors
            closeButton
            style={
                {
                    "--normal-bg": "var(--card)",
                    "--normal-text": "var(--foreground)",
                    "--normal-border": "var(--border)",
                } as React.CSSProperties
            }
            {...props}
        />
    );
};

export { Toaster };
