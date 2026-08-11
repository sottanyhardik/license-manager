import { useState, type FormEvent } from "react";
import { AlertCircle, CheckCircle2, Eye, EyeOff, Lock, Loader2, X } from "lucide-react";

import api from "../api/axios";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface ChangePasswordFormProps {
    onSuccess?: () => void;
}

export default function ChangePasswordForm({ onSuccess }: ChangePasswordFormProps) {
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showCurrent, setShowCurrent] = useState(false);
    const [showNew, setShowNew] = useState(false);
    const [showConfirm, setShowConfirm] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState(false);

    const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        setError("");
        setSuccess(false);

        // Frontend validation
        if (!currentPassword || !newPassword || !confirmPassword) {
            setError("All fields are required.");
            return;
        }

        if (newPassword !== confirmPassword) {
            setError("New passwords do not match.");
            return;
        }

        if (newPassword.length < 8) {
            setError("New password must be at least 8 characters.");
            return;
        }

        setLoading(true);
        try {
            await api.post("/auth/change-password/", {
                current_password: currentPassword,
                new_password: newPassword,
            });
            setSuccess(true);
            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");
            if (onSuccess) {
                setTimeout(onSuccess, 1500);
            }
        } catch (err) {
            const detail =
                (err as { response?: { data?: { detail?: string | string[] } } })
                    .response?.data?.detail || "Failed to change password.";
            setError(Array.isArray(detail) ? detail[0] : detail);
        } finally {
            setLoading(false);
        }
    };

    if (success) {
        return (
            <Card>
                <CardHeader className="border-b">
                    <CardTitle className="text-sm">Change Password</CardTitle>
                </CardHeader>
                <CardContent className="pt-6 text-center">
                    <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-success/10">
                        <CheckCircle2 className="size-6 text-success" />
                    </div>
                    <h3 className="font-semibold text-foreground">Password Changed</h3>
                    <p className="mt-1.5 text-sm text-muted-foreground">
                        Your password has been changed successfully.
                    </p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader className="border-b">
                <CardTitle className="text-sm">Change Password</CardTitle>
            </CardHeader>
            <CardContent className="pt-5">
                {error && (
                    <div
                        role="alert"
                        className="mb-4 flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive"
                    >
                        <AlertCircle className="mt-0.5 size-4 shrink-0" />
                        <span>{error}</span>
                    </div>
                )}

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                    {/* Current Password */}
                    <div>
                        <Label htmlFor="current-password" className="mb-1.5 flex items-center gap-1.5">
                            <Lock className="size-3.5" />
                            Current Password
                        </Label>
                        <div className="relative">
                            <Input
                                id="current-password"
                                type={showCurrent ? "text" : "password"}
                                value={currentPassword}
                                onChange={(e) => setCurrentPassword(e.target.value)}
                                placeholder="Enter current password"
                                required
                                autoComplete="current-password"
                                disabled={loading}
                                className="pr-10"
                            />
                            <button
                                type="button"
                                onClick={() => setShowCurrent(!showCurrent)}
                                aria-label={showCurrent ? "Hide password" : "Show password"}
                                className="absolute inset-y-0 right-0 flex items-center justify-center pr-3 text-muted-foreground transition-colors hover:text-foreground"
                                disabled={loading}
                            >
                                {showCurrent ? (
                                    <EyeOff className="size-4" />
                                ) : (
                                    <Eye className="size-4" />
                                )}
                            </button>
                        </div>
                    </div>

                    {/* New Password */}
                    <div>
                        <Label htmlFor="new-password" className="mb-1.5 flex items-center gap-1.5">
                            <Lock className="size-3.5" />
                            New Password
                        </Label>
                        <div className="relative">
                            <Input
                                id="new-password"
                                type={showNew ? "text" : "password"}
                                value={newPassword}
                                onChange={(e) => setNewPassword(e.target.value)}
                                placeholder="Enter new password"
                                required
                                autoComplete="new-password"
                                disabled={loading}
                                className="pr-10"
                            />
                            <button
                                type="button"
                                onClick={() => setShowNew(!showNew)}
                                aria-label={showNew ? "Hide password" : "Show password"}
                                className="absolute inset-y-0 right-0 flex items-center justify-center pr-3 text-muted-foreground transition-colors hover:text-foreground"
                                disabled={loading}
                            >
                                {showNew ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                            </button>
                        </div>
                        <p className="mt-1.5 text-[11.5px] text-muted-foreground">
                            Minimum 8 characters. Use a strong password with letters, numbers, and symbols.
                        </p>
                    </div>

                    {/* Confirm Password */}
                    <div>
                        <Label htmlFor="confirm-password" className="mb-1.5 flex items-center gap-1.5">
                            <Lock className="size-3.5" />
                            Confirm New Password
                        </Label>
                        <div className="relative">
                            <Input
                                id="confirm-password"
                                type={showConfirm ? "text" : "password"}
                                value={confirmPassword}
                                onChange={(e) => setConfirmPassword(e.target.value)}
                                placeholder="Confirm new password"
                                required
                                autoComplete="new-password"
                                disabled={loading}
                                className="pr-10"
                            />
                            <button
                                type="button"
                                onClick={() => setShowConfirm(!showConfirm)}
                                aria-label={showConfirm ? "Hide password" : "Show password"}
                                className="absolute inset-y-0 right-0 flex items-center justify-center pr-3 text-muted-foreground transition-colors hover:text-foreground"
                                disabled={loading}
                            >
                                {showConfirm ? (
                                    <EyeOff className="size-4" />
                                ) : (
                                    <Eye className="size-4" />
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Submit Button */}
                    <Button type="submit" disabled={loading} className="w-full">
                        {loading ? (
                            <>
                                <Loader2 className="size-4 animate-spin" />
                                Changing…
                            </>
                        ) : (
                            <>
                                <Lock className="size-4" />
                                Change Password
                            </>
                        )}
                    </Button>
                </form>
            </CardContent>
        </Card>
    );
}
