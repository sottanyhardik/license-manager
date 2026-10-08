import "./App.css";

import { BrowserRouter } from "react-router-dom";

import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import { ParsingStatusProvider } from "./context/ParsingStatusContext";
import ErrorBoundary from "./components/ErrorBoundary";
import AppRoutes from "./routes/AppRoutes";
import { Toaster } from "@/components/ui/sonner";

export default function App() {
    return (
        <ThemeProvider>
            <AuthProvider>
                <ParsingStatusProvider>
                    <BrowserRouter>
                        <Toaster duration={3500} />
                        <ErrorBoundary>
                            <AppRoutes />
                        </ErrorBoundary>
                    </BrowserRouter>
                </ParsingStatusProvider>
            </AuthProvider>
        </ThemeProvider>
    );
}
