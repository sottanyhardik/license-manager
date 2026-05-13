import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";

// Bootstrap
import "bootstrap/dist/css/bootstrap.min.css";
import "bootstrap/dist/js/bootstrap.bundle.min.js";
import "bootstrap-icons/font/bootstrap-icons.css";

// App‑wide design tokens (loaded LAST so it wins specificity)
import "./theme/tabler.css";

// Global Styles (optional)
// import "./assets/styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
        <App/>
    </React.StrictMode>
);
