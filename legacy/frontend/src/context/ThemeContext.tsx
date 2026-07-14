import { createContext, useContext, useEffect, useState } from "react";

// eslint-disable-next-line react-refresh/only-export-components
export const ThemeContext = createContext({ theme: "light", toggleTheme: () => {} });

export function ThemeProvider({ children }) {
    const [theme, setTheme] = useState(() => {
        const saved = localStorage.getItem("theme");
        if (saved === "light" || saved === "dark") return saved;
        return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    });

    useEffect(() => {
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);
    }, [theme]);

    const toggleTheme = () => setTheme(t => t === "light" ? "dark" : "light");

    return (
        <ThemeContext.Provider value={{ theme, toggleTheme }}>
            {children}
        </ThemeContext.Provider>
    );
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => useContext(ThemeContext);
