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
                className="relative hidden w-[440px] shrink-0 flex-col justify-between overflow-hidden p-12 text-white lg:flex"
                style={{
                    background:
                        "linear-gradient(145deg, #1E3A5F 0%, var(--tb-brand-active) 55%, var(--tb-brand) 100%)",
                }}
                aria-hidden="true"
            >
                {/* Decorative blobs */}
                <div className="pointer-events-none absolute -right-28 -top-28 size-96 rounded-full bg-white/[0.06]" />
                <div className="pointer-events-none absolute -bottom-20 -left-20 size-72 rounded-full bg-white/[0.04]" />

                <div className="relative z-10 flex items-center gap-3 text-lg font-semibold tracking-tight">
                    <span className="flex size-10 items-center justify-center rounded-xl border border-white/20 bg-white/15 backdrop-blur-sm">
                        <ShieldCheck className="size-5" />
                    </span>
                    License Manager
                </div>

                <div className="relative z-10">
                    <h2 className="mb-3 text-3xl font-bold leading-tight tracking-tight text-white">
                        Trade compliance,<br />simplified.
                    </h2>
                    <p className="max-w-sm text-[15px] leading-relaxed text-white/70">
                        Manage EPCG, advance licenses, BOE entries, allotments,
                        and SION norms in one unified platform.
                    </p>
                </div>

                <ul className="relative z-10 flex flex-col gap-2.5">
                    {FEATURES.map((f) => (
                        <li key={f} className="flex items-center gap-2.5 text-[13px] text-white/85">
                            <span className="size-1.5 shrink-0 rounded-full bg-white/60" />
                            {f}
                        </li>
                    ))}
                </ul>
            </aside>

            {/* Form panel */}
            <div className="flex flex-1 items-center justify-center px-6 py-8">
                <motion.div
                    className="w-full max-w-sm"
                    initial={reduce ? false : { opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                >
                    {/* Header */}
                    <div className="mb-8 text-center">
                        <div className="mx-auto mb-4 flex size-13 items-center justify-center rounded-2xl border border-primary/15 bg-primary/10 text-primary">
                            <ShieldCheck className="size-6" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-foreground">
                            Welcome back
                        </h1>
                        <p className="mt-1 text-sm text-muted-foreground">
                            Sign in to your account
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

                    <p className="mt-7 text-center text-[11.5px] text-muted-foreground/70">
                        License Manager · Built by Hardik Sottany
                    </p>
                </motion.div>
            </div>
        </div>
    );
}
