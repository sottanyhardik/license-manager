import { useContext, useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { Button } from "../components/ui";

export default function Login() {
    const { user, loading: authLoading, loginSuccess } = useContext(AuthContext);
    const navigate = useNavigate();
    const location = useLocation();
    const [form, setForm] = useState({ username: "", password: "" });
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);

    const searchParams = new URLSearchParams(location.search);
    const redirectParam = searchParams.get("redirect");
    const reason = searchParams.get("reason");
    const from = location.state?.from || redirectParam || "/dashboard";

    const sessionMessage =
        reason === "idle" ? "You were logged out due to inactivity. Please log in again." :
        reason === "session_expired" ? "Your session has expired. Please log in again." :
        null;

    useEffect(() => { document.title = "Login | License Manager"; }, []);

    useEffect(() => {
        if (!authLoading && user) {
            navigate(from, { replace: true });
        }
    }, [user, authLoading, navigate, from]);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setSubmitting(true);
        try {
            const { data } = await api.post("/auth/login/", form);
            loginSuccess({ access: data.access, refresh: data.refresh, user: data.user });
            navigate(from, { replace: true });
        } catch (err) {
            setError(err.response?.data?.detail || "Invalid username or password");
            setSubmitting(false);
        }
    };

    return (
        <div
            style={{
                minHeight: "100vh",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "var(--tb-body-bg)",
                padding: "20px",
            }}
        >
            <div
                className="card"
                style={{
                    maxWidth: 440,
                    width: "100%",
                    overflow: "hidden",
                    boxShadow: "var(--tb-shadow-overlay)",
                }}
            >
                {/* Header */}
                <div
                    style={{
                        background: `linear-gradient(135deg, var(--tb-brand) 0%, var(--tb-brand-active) 100%)`,
                        padding: "36px 28px",
                        textAlign: "center",
                        color: "#fff",
                    }}
                >
                    <div
                        aria-hidden="true"
                        style={{
                            width: 64,
                            height: 64,
                            margin: "0 auto 16px",
                            borderRadius: 14,
                            background: "rgba(255, 255, 255, 0.18)",
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "center",
                            backdropFilter: "blur(8px)",
                        }}
                    >
                        <i className="bi bi-shield-check" style={{ fontSize: "2rem" }} />
                    </div>
                    <h2 style={{ fontSize: "1.5rem", fontWeight: 600, margin: 0, color: "#fff" }}>
                        Welcome Back
                    </h2>
                    <p style={{ fontSize: "0.9rem", opacity: 0.92, marginTop: 4, marginBottom: 0 }}>
                        License Manager
                    </p>
                </div>

                {/* Body */}
                <div style={{ padding: "28px 28px 20px" }}>
                    {sessionMessage && (
                        <div className="alert alert-warning d-flex align-items-center" role="alert">
                            <i className="bi bi-clock-history me-2" aria-hidden="true" />
                            <span>{sessionMessage}</span>
                        </div>
                    )}
                    {error && (
                        <div className="alert alert-danger d-flex align-items-center" role="alert">
                            <i className="bi bi-exclamation-circle-fill me-2" aria-hidden="true" />
                            <span>{error}</span>
                        </div>
                    )}

                    <form onSubmit={submit} className="form-group-material" style={{ margin: 0 }}>
                        <div className="mb-3">
                            <label className="form-label" htmlFor="login-username">
                                <i className="bi bi-person me-1" aria-hidden="true" /> Username
                            </label>
                            <input
                                id="login-username"
                                className="form-control"
                                placeholder="Enter your username"
                                value={form.username}
                                onChange={e => setForm({ ...form, username: e.target.value })}
                                required
                                autoFocus
                                autoComplete="username"
                            />
                        </div>

                        <div className="mb-4">
                            <label className="form-label" htmlFor="login-password">
                                <i className="bi bi-lock me-1" aria-hidden="true" /> Password
                            </label>
                            <input
                                id="login-password"
                                type="password"
                                className="form-control"
                                placeholder="Enter your password"
                                value={form.password}
                                onChange={e => setForm({ ...form, password: e.target.value })}
                                required
                                autoComplete="current-password"
                            />
                        </div>

                        <Button
                            type="submit"
                            variant="primary"
                            block
                            loading={submitting}
                            icon={submitting ? null : "box-arrow-in-right"}
                            disabled={submitting}
                        >
                            {submitting ? "Logging in…" : "Login"}
                        </Button>
                    </form>
                </div>

                {/* Footer */}
                <div
                    style={{
                        padding: "16px 28px",
                        background: "var(--tb-sunken)",
                        textAlign: "center",
                        borderTop: "1px solid var(--tb-border-soft)",
                    }}
                >
                    <small style={{ color: "var(--tb-text-secondary)" }}>
                        Built by Hardik Sottany
                    </small>
                </div>
            </div>
        </div>
    );
}
