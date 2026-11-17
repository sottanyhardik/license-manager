import "./App.css";

import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ParsingStatusProvider } from "./context/ParsingStatusContext";
import ErrorBoundary from "./components/ErrorBoundary";
import AppRoutes from "./routes/AppRoutes";
import { ConfirmProvider } from "@/components/shared/ConfirmDialog";
import { Toaster } from "@/components/ui/sonner";

export default function App() {
    return (
        <ThemeProvider>
            <AuthProvider>
                <ParsingStatusProvider>
                    <ConfirmProvider>
                        <BrowserRouter>
                            <Toaster duration={3500} />
                            <ErrorBoundary>
                                <AppRoutes />
                            </ErrorBoundary>
                        </BrowserRouter>
                    </ConfirmProvider>
                </ParsingStatusProvider>
            </AuthProvider>
        </ThemeProvider>
    );
}
