import "./App.css";

import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import ErrorBoundary from "./components/ErrorBoundary";
import AppRoutes from "./routes/AppRoutes";
import { Toaster } from "@/components/ui/sonner";

export default function App() {
    return (
        <ThemeProvider>
            <AuthProvider>
                <BrowserRouter>
                    <Toaster duration={3500} />
                    <ErrorBoundary>
                        <AppRoutes />
                    </ErrorBoundary>
                </BrowserRouter>
            </AuthProvider>
        </ThemeProvider>
    );
}
