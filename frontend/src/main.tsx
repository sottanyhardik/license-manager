import React, { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { queryClient } from "./api/queryClient";

// Base reset
import "./index.css";

// Bootstrap Icons — keep for bi-* icon references still in the codebase

// Design system tokens + component overrides
import "./theme/tabler.css";

// Tailwind v4 + shadcn (now primary CSS layer — Bootstrap CSS removed)
import "./styles/tailwind.css";

// Devtools are valuable locally but should never be parsed or transferred by
// a production client.  A development-only lazy boundary also keeps them out
// of the application shell during normal development until explicitly needed.
const ReactQueryDevtools = import.meta.env.DEV
    ? lazy(() => import("@tanstack/react-query-devtools").then((module) => ({ default: module.ReactQueryDevtools })))
    : null;

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
        <QueryClientProvider client={queryClient}>
            <App />
            {ReactQueryDevtools && (
                <Suspense fallback={null}>
                    <ReactQueryDevtools initialIsOpen={false} />
                </Suspense>
            )}
        </QueryClientProvider>
    </React.StrictMode>
);
