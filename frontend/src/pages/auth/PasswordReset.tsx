import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { motion, useReducedMotion } from "framer-motion";
import { KeyRound, Mail, Send, Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";

import api from "../../api/axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function PasswordReset() {
    const navigate = useNavigate();
    const reduce = useReducedMotion();
    const [email, setEmail] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [sent, setSent] = useState(false);

    const submit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            await api.post("/auth/password-reset/", { email });
            setSent(true);
            toast.success("Reset instructions sent to your email.");
        } catch {
            toast.error("Error sending reset email");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div className="flex min-h-screen items-center justify-center bg-background px-6">
            <motion.div
                className="w-full max-w-sm"
                initial={reduce ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
            >
                <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-xl">
                    {/* Header */}
                    <div className="bg-gradient-to-br from-blue-700 to-blue-600 px-8 py-9 text-center text-white">
                        <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-2xl border border-white/20 bg-white/15 backdrop-blur-sm">
                            <KeyRound className="size-7" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-white">Forgot Password</h1>
                        <p className="mt-1.5 text-sm text-white/80">Enter your email to receive reset instructions</p>
                    </div>

                    {/* Body */}
                    <div className="p-8">
                        {sent ? (
                            <div className="text-center">
                                <div className="mx-auto mb-4 flex size-16 items-center justify-center rounded-full bg-success/10">
                                    <CheckCircle2 className="size-8 text-success" />
                                </div>
                                <h2 className="mb-1.5 font-semibold text-foreground">Check Your Email</h2>
                                <p className="mb-6 text-[13px] text-muted-foreground">
                                    Reset instructions have been sent to <strong className="text-foreground">{email}</strong>.
                                </p>
                                <Button variant="outline" className="w-full" onClick={() => navigate("/login")}>
                                    <ArrowLeft className="size-4" />Back to Login
                                </Button>
                            </div>
                        ) : (
                            <form onSubmit={submit} className="flex flex-col gap-4">
                                <div>
                                    <Label className="mb-1.5 flex items-center gap-1.5" htmlFor="reset-email">
                                        <Mail className="size-3.5" />Email Address
                                    </Label>
                                    <Input
                                        id="reset-email"
                                        type="email"
                                        className="h-10"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        placeholder="Enter your email"
                                        required
                                        autoComplete="email"
                                        autoFocus
                                    />
                                </div>
                                <Button type="submit" size="lg" className="w-full" disabled={submitting}>
                                    {submitting ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
                                    {submitting ? "Sending…" : "Send Reset Email"}
                                </Button>
                                <Button type="button" variant="link" className="mx-auto text-muted-foreground" onClick={() => navigate("/login")}>
                                    <ArrowLeft className="size-3.5" />Back to Login
                                </Button>
                            </form>
                        )}
                    </div>

                    <div className="border-t border-border/70 bg-muted/40 px-8 py-3.5 text-center">
                        <span className="text-[11.5px] text-muted-foreground">License Manager System</span>
                    </div>
                </div>
            </motion.div>
        </div>
    );
}
