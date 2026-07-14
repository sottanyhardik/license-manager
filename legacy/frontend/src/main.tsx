import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import App from "./App";
import { queryClient } from "./api/queryClient";

// Base reset
import "./index.css";

// Bootstrap Icons — keep for bi-* icon references still in the codebase

// Design system tokens + component overrides
import "./theme/tabler.css";

// Tailwind v4 + shadcn (now primary CSS layer — Bootstrap CSS removed)
import "./styles/tailwind.css";

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
        <QueryClientProvider client={queryClient}>
            <App />
            {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
        </QueryClientProvider>
    </React.StrictMode>
);
