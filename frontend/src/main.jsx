import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// Base reset
import "./index.css";

// Bootstrap
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/js/bootstrap.bundle.min.js";
import "bootstrap-icons/font/bootstrap-icons.css";

// Design system (loaded LAST — wins specificity over Bootstrap)
import "./theme/tabler.css";

// Tailwind v4 + shadcn utilities (layered — coexists with Bootstrap
// during migration; utilities target shadcn components only)
import "./styles/tailwind.css";

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
