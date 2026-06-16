import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// Base reset
import "./index.css";

// Bootstrap Icons — keep for bi-* icon references still in the codebase
import "bootstrap-icons/font/bootstrap-icons.css";

// Design system tokens + component overrides
import "./theme/tabler.css";

// Tailwind v4 + shadcn (now primary CSS layer — Bootstrap CSS removed)
import "./styles/tailwind.css";

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
