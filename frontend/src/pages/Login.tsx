import { type FormEvent, useContext, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "framer-motion";
import {
    ShieldCheck,
    Eye,
    EyeOff,
    LogIn,
    Loader2,
    Clock,
    AlertCircle,
} from "lucide-react";

import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { getSafeRedirect } from "../utils/authRedirect";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const FEATURES = [
    "License lifecycle management",
    "Bill of Entry tracking",
    "Allotment & utilization reports",
    "SION norm compliance",
    "Role-based access control",
];

export default function Login() {
    const { user, loading: authLoading, loginSuccess } = useContext(AuthContext);
    const navigate = useNavigate();
    const location = useLocation();
    const reduce = useReducedMotion();

    const [form, setForm] = useState({ username: "", password: "" });
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    const searchParams = new URLSearchParams(location.search);
    const redirectParam = searchParams.get("redirect");
    const reason = searchParams.get("reason");
    const from = getSafeRedirect(location.state?.from) ?? getSafeRedirect(redirectParam) ?? "/dashboard";

    const sessionMessage =
        reason === "idle" ? "You were logged out due to inactivity." :
        reason === "session_expired" ? "Your session has expired. Please log in again." :
        null;

    useEffect(() => { document.title = "Sign In · License Manager"; }, []);

    useEffect(() => {
        if (!authLoading && user) navigate(from, { replace: true });
    }, [user, authLoading, navigate, from]);

    const submit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setError("");
        setSubmitting(true);
        try {
            const { data } = await api.post("/auth/login/", form);
            loginSuccess({ access: data.access, refresh: data.refresh, user: data.user });
            navigate(from, { replace: true });
        } catch (err) {
            const detail = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
            setError(detail || "Invalid username or password.");
            setSubmitting(false);
        }
    };

    return (
        <div className="flex min-h-screen bg-background">
            {/* Brand panel — hidden below lg */}
            <aside
                className="relative hidden w-[420px] shrink-0 flex-col overflow-hidden lg:flex"
                style={{
                    background:
                        "linear-gradient(160deg, #0F2545 0%, #1E3A6E 40%, #1D4ED8 80%, #2563EB 100%)",
                }}
                aria-hidden="true"
            >
                {/* Decorative geometric grid overlay */}
                <div
                    className="pointer-events-none absolute inset-0 opacity-[0.06]"
                    style={{
                        backgroundImage:
                            "linear-gradient(rgba(255,255,255,0.4) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.4) 1px, transparent 1px)",
                        backgroundSize: "32px 32px",
                    }}
                />
                {/* Top-right radial glow */}
                <div className="pointer-events-none absolute -right-24 -top-24 size-80 rounded-full bg-blue-400/20 blur-3xl" />
                {/* Bottom-left glow */}
                <div className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-indigo-900/50 blur-3xl" />

                {/* Brand mark — top */}
                <div className="relative z-10 flex-shrink-0 p-10 pb-0">
                    <div className="flex items-center gap-3">
                        <span className="flex size-9 items-center justify-center rounded-xl border border-white/25 bg-white/20 backdrop-blur-sm">
                            <ShieldCheck className="size-4.5 text-white" />
                        </span>
                        <span className="text-[15px] font-semibold tracking-tight text-white">
                            License Manager
                        </span>
                    </div>
                </div>

                {/* Center content */}
                <div className="relative z-10 flex flex-1 flex-col justify-center px-10">
                    <div className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-[11px] font-medium uppercase tracking-widest text-white/70">
                        <span className="size-1.5 rounded-full bg-emerald-400" />
                        Trade Operations Platform
                    </div>
                    <h2 className="mt-4 text-[2rem] font-bold leading-[1.2] tracking-tight text-white">
                        Trade compliance,<br />
                        <span className="text-blue-200">simplified.</span>
                    </h2>
                    <p className="mt-4 max-w-[280px] text-[14px] leading-relaxed text-white/65">
                        Manage EPCG, advance licenses, BOE entries, allotments,
                        and SION norms in one unified platform.
                    </p>

                    {/* Feature list */}
                    <ul className="mt-8 flex flex-col gap-3">
                        {FEATURES.map((f) => (
                            <li key={f} className="flex items-center gap-3 text-[13px] text-white/80">
                                <span className="flex size-5 shrink-0 items-center justify-center rounded-full bg-white/15">
                                    <svg className="size-2.5 text-white" viewBox="0 0 10 8" fill="none">
                                        <path d="M1 4l2.5 2.5L9 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                                    </svg>
                                </span>
                                {f}
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Bottom bar */}
                <div className="relative z-10 flex-shrink-0 border-t border-white/10 px-10 py-5">
                    <p className="text-[11px] text-white/40">
                        © 2025 License Manager · All rights reserved
                    </p>
                </div>
            </aside>

            {/* Form panel — uses background color to contrast with body */}
            <div className="flex flex-1 flex-col items-center justify-center bg-background px-6 py-10">
                <motion.div
                    className="w-full max-w-[400px]"
                    initial={reduce ? false : { opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
                >
                    {/* Form card — lifted card gives visual grounding */}
                    <div className="rounded-2xl border border-border/70 bg-card p-8 shadow-[0_2px_16px_rgba(0,0,0,0.06),0_1px_4px_rgba(0,0,0,0.04)]">
                        {/* Header */}
                        <div className="mb-7">
                            <div className="mb-4 flex size-11 items-center justify-center rounded-xl border border-primary/15 bg-primary/10 text-primary">
                                <ShieldCheck className="size-5" />
                            </div>
                            <h1 className="text-[1.5rem] font-bold leading-tight tracking-tight text-foreground">
                                Welcome back
                            </h1>
                            <p className="mt-1.5 text-sm text-muted-foreground">
                                Sign in to continue to License Manager
                            </p>
                        </div>

                    {/* Session alert */}
                    {sessionMessage && (
                        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-warning/30 bg-warning/10 px-3.5 py-2.5 text-[13px] text-warning">
                            <Clock className="mt-0.5 size-4 shrink-0" />
                            <span>{sessionMessage}</span>
                        </div>
                    )}

                    {/* Error */}
                    {error && (
                        <div className="mb-4 flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                            <AlertCircle className="mt-0.5 size-4 shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}

                    {/* Form */}
                    <form onSubmit={submit} noValidate className="flex flex-col gap-5">
                        <div className="flex flex-col gap-1.5">
                            <Label htmlFor="login-username">Username</Label>
                            <Input
                                id="login-username"
                                placeholder="Enter your username"
                                value={form.username}
                                onChange={(e) => setForm({ ...form, username: e.target.value })}
                                required
                                autoFocus
                                autoComplete="username"
                                className="h-10"
                            />
                        </div>

                        <div className="flex flex-col gap-1.5">
                            <Label htmlFor="login-password">Password</Label>
                            <div className="relative">
                                <Input
                                    id="login-password"
                                    type={showPassword ? "text" : "password"}
                                    placeholder="Enter your password"
                                    value={form.password}
                                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                                    required
                                    autoComplete="current-password"
                                    className="h-10 pr-10"
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowPassword((v) => !v)}
                                    aria-label={showPassword ? "Hide password" : "Show password"}
                                    className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground transition-colors hover:text-foreground cursor-pointer"
                                >
                                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                                </button>
                            </div>
                        </div>

                        <div className="-mt-2 text-right">
                            <Link to="/forgot-password" className="text-xs font-medium text-primary hover:underline">
                                Forgot password?
                            </Link>
                        </div>

                        <Button type="submit" size="lg" disabled={submitting} className="mt-1 w-full">
                            {submitting ? (
                                <>
                                    <Loader2 className="size-4 animate-spin" />
                                    Signing in…
                                </>
                            ) : (
                                <>
                                    <LogIn className="size-4" />
                                    Sign in
                                </>
                            )}
                        </Button>
                    </form>
                    </div>{/* end form card */}

                    <p className="mt-5 text-center text-[11px] text-muted-foreground/50">
                        License Manager · Secure sign-in
                    </p>
                </motion.div>
            </div>
        </div>
    );
}
