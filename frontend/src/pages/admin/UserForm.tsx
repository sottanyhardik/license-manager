import { useContext, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Check, X, KeyRound, ShieldCheck, UserRound } from "lucide-react";

import { createUser, getAvailableRoles, getUser, resetPassword, updateUser } from "../../api/users";
import { AuthContext } from "../../context/AuthContext";
import { getErrorMessage } from "../../utils/errorUtils";
import { extractFormErrors, getFieldError } from "../../utils/formErrors";
import { ROLE_LABELS } from "../../utils/roleConstants";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Checkbox } from "@/components/ui/checkbox";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type UserFormData = {
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    password: string;
    is_active: boolean;
    is_staff: boolean;
    is_superuser: boolean;
    roles: string[];
};

const emptyForm: UserFormData = {
    username: "", email: "", first_name: "", last_name: "", password: "",
    is_active: true, is_staff: false, is_superuser: false, roles: [],
};

export default function UserForm() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user: currentUser } = useContext(AuthContext);
    const isEdit = Boolean(id);

    const [form, setForm] = useState<UserFormData>(emptyForm);
    const [availableRoles, setAvailableRoles] = useState<string[]>([]);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [resettingPw, setResettingPw] = useState(false);
    const [newPassword, setNewPassword] = useState("");
    const [showPwReset, setShowPwReset] = useState(false);
    const [fieldErrors, setFieldErrors] = useState<Record<string, string | undefined>>({});
    const [passwordResetErrors, setPasswordResetErrors] = useState<Record<string, string | undefined>>({});

    useEffect(() => {
        const init = async () => {
            setLoading(true);
            try {
                const [{ data: roles }] = await Promise.all([getAvailableRoles()]);
                setAvailableRoles(roles);
                if (isEdit) {
                    const { data: user } = await getUser(id);
                    setForm({
                        username: user.username ?? "",
                        email: user.email ?? "",
                        first_name: user.first_name ?? "",
                        last_name: user.last_name ?? "",
                        password: "",
                        is_active: user.is_active,
                        is_staff: user.is_staff ?? false,
                        is_superuser: user.is_superuser ?? false,
                        roles: user.roles ?? [],
                    });
                }
            } catch (err: unknown) {
                toast.error(getErrorMessage(err as Error));
            } finally {
                setLoading(false);
            }
        };
        init();
    }, [id, isEdit]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const { name, value, type, checked } = e.target;
        setForm(prev => ({ ...prev, [name]: type === "checkbox" ? checked : value }));
        setFieldErrors(prev => ({ ...prev, [name]: undefined }));
    };

    const setFlag = (name: keyof UserFormData, checked: boolean) => setForm(prev => ({ ...prev, [name]: checked }));

    const toggleRole = (code: string) => {
        setForm(prev => ({
            ...prev,
            roles: prev.roles.includes(code) ? prev.roles.filter(r => r !== code) : [...prev.roles, code],
        }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setFieldErrors({});
        try {
            const payload = { ...form };
            if (isEdit && !payload.password) delete payload.password;
            if (isEdit) {
                await updateUser(id, payload);
                toast.success("User updated");
            } else {
                await createUser(payload);
                toast.success("User created");
            }
            navigate("/admin/users");
        } catch (err: unknown) {
            const { fieldErrors: errors } = extractFormErrors(err);
            setFieldErrors(errors);
            toast.error(getErrorMessage(err as Error));
        } finally {
            setSaving(false);
        }
    };

    const handleResetPassword = async () => {
        if (!newPassword) return;
        setResettingPw(true);
        setPasswordResetErrors({});
        try {
            await resetPassword(id, newPassword);
            toast.success("Password reset successfully");
            setShowPwReset(false);
            setNewPassword("");
        } catch (err: unknown) {
            const { fieldErrors: errors } = extractFormErrors(err);
            setPasswordResetErrors(errors);
            toast.error(getErrorMessage(err as Error));
        } finally {
            setResettingPw(false);
        }
    };

    if (loading) return <div className="p-8 text-center text-sm text-muted-foreground">Loading…</div>;

    const FieldError = ({ name }: { name: string }) => {
        const error = getFieldError(fieldErrors, name);
        return error ? <p className="mt-1 text-[11.5px] text-destructive">{error}</p> : null;
    };

    return (
        <div className="mx-auto max-w-4xl pb-20">
            <div className="mb-5 border-b border-border pb-4">
                <Button variant="ghost" size="sm" className="mb-3 -ml-2" onClick={() => navigate("/admin/users")}>
                    <ArrowLeft className="size-4" />
                    Back to users
                </Button>
                <div className="flex items-start gap-3">
                    <div className="flex size-10 shrink-0 items-center justify-center rounded-lg border border-primary/15 bg-primary/10 text-primary">
                        <UserRound className="size-5" aria-hidden="true" />
                    </div>
                    <div>
                        <h1 className="text-xl font-semibold tracking-tight text-foreground">{isEdit ? "Edit user access" : "Create user"}</h1>
                        <p className="mt-0.5 text-[13px] text-muted-foreground">Manage account details, operational roles, and access flags.</p>
                    </div>
                </div>
            </div>

            <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                {/* Account details */}
                <Card>
                    <CardHeader className="flex-row items-center gap-2 border-b py-3"><UserRound className="size-4 text-muted-foreground" aria-hidden="true" /><CardTitle className="text-sm">Account details</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 gap-3 pt-4 sm:grid-cols-2">
                        <div>
                            <Label className="mb-1.5 required" htmlFor="username">Username</Label>
                            <Input id="username" name="username" value={form.username} onChange={handleChange}
                                   required autoComplete="off" aria-invalid={!!fieldErrors.username} />
                            <FieldError name="username" />
                        </div>
                        <div>
                            <Label className="mb-1.5" htmlFor="email">Email</Label>
                            <Input id="email" type="email" name="email" value={form.email} onChange={handleChange}
                                   autoComplete="off" aria-invalid={!!fieldErrors.email} />
                            <FieldError name="email" />
                        </div>
                        <div>
                            <Label className="mb-1.5" htmlFor="first_name">First Name</Label>
                            <Input id="first_name" name="first_name" value={form.first_name} onChange={handleChange} />
                        </div>
                        <div>
                            <Label className="mb-1.5" htmlFor="last_name">Last Name</Label>
                            <Input id="last_name" name="last_name" value={form.last_name} onChange={handleChange} />
                        </div>
                        {!isEdit && (
                            <div>
                                <Label className="mb-1.5" htmlFor="password">Password</Label>
                                <Input id="password" type="password" name="password" value={form.password}
                                       onChange={handleChange} autoComplete="new-password" aria-invalid={!!fieldErrors.password} />
                                <FieldError name="password" />
                            </div>
                        )}
                    </CardContent>
                </Card>

                {/* Access flags */}
                <Card>
                    <CardHeader className="flex-row items-center gap-2 border-b py-3"><ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" /><CardTitle className="text-sm">Access flags</CardTitle></CardHeader>
                    <CardContent className="flex flex-wrap gap-x-8 gap-y-3 pt-4">
                        <label className="flex cursor-pointer items-center gap-2.5 text-sm">
                            <Switch checked={form.is_active} onCheckedChange={(c) => setFlag("is_active", c)} />
                            Active
                        </label>
                        <label className="flex cursor-pointer items-center gap-2.5 text-sm">
                            <Switch checked={form.is_staff} onCheckedChange={(c) => setFlag("is_staff", c)} />
                            Staff (Django admin)
                        </label>
                        {currentUser?.is_superuser && (
                            <label className="flex cursor-pointer items-center gap-2.5 text-sm">
                                <Switch checked={form.is_superuser} onCheckedChange={(c) => setFlag("is_superuser", c)} />
                                Super Admin (bypasses all role checks)
                            </label>
                        )}
                    </CardContent>
                </Card>

                {/* Roles */}
                <Card>
                    <CardHeader className="flex-row items-center gap-2 border-b py-3"><ShieldCheck className="size-4 text-muted-foreground" aria-hidden="true" /><CardTitle className="text-sm">Roles</CardTitle></CardHeader>
                    <CardContent className="grid grid-cols-1 gap-2 pt-4 sm:grid-cols-2 lg:grid-cols-3">
                        {availableRoles.map((code) => {
                            const checked = form.roles.includes(code);
                            return (
                                <label
                                    key={code}
                                    className={cn(
                                        "flex cursor-pointer items-center gap-2.5 rounded-md border px-3 py-2 text-[13px] transition-colors",
                                        checked ? "border-primary/50 bg-primary/10 text-foreground" : "border-border text-muted-foreground hover:bg-accent/50"
                                    )}
                                >
                                    <Checkbox checked={checked} onCheckedChange={() => toggleRole(code)} />
                                    {ROLE_LABELS[code] ?? code}
                                </label>
                            );
                        })}
                    </CardContent>
                </Card>

                <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-background/95 px-4 py-3 shadow-sm backdrop-blur sm:left-[var(--sidebar-width,0px)] sm:px-6">
                  <div className="mx-auto flex max-w-4xl flex-wrap gap-2">
                    <Button type="submit" disabled={saving}>
                        <Check className="size-4" />
                        {saving ? "Saving…" : isEdit ? "Save Changes" : "Create User"}
                    </Button>
                    <Button type="button" variant="outline" onClick={() => navigate("/admin/users")}>
                        <X className="size-4" />
                        Cancel
                    </Button>
                    {isEdit && (
                        <Button type="button" variant="outline" className="ml-auto" onClick={() => setShowPwReset(v => !v)}>
                            <KeyRound className="size-4" />
                            Reset Password
                        </Button>
                    )}
                  </div>
                </div>
            </form>

            {/* Inline password reset */}
            {showPwReset && (
                <Card className="mt-4">
                    <CardHeader className="border-b"><CardTitle className="text-sm text-warning">Reset Password</CardTitle></CardHeader>
                    <CardContent className="flex flex-wrap gap-2 pt-5">
                        <Input
                            type="password"
                            className="flex-1"
                            placeholder="New password"
                            value={newPassword}
                            onChange={(e) => {
                                setNewPassword(e.target.value);
                                setPasswordResetErrors(prev => ({ ...prev, password: undefined }));
                            }}
                            autoComplete="new-password"
                            aria-invalid={!!getFieldError(passwordResetErrors, "password")}
                        />
                        {getFieldError(passwordResetErrors, "password") && (
                            <p className="basis-full text-[11.5px] text-destructive">
                                {getFieldError(passwordResetErrors, "password")}
                            </p>
                        )}
                        <Button onClick={handleResetPassword} disabled={resettingPw || !newPassword}>
                            <Check className="size-4" />
                            {resettingPw ? "Saving…" : "Set Password"}
                        </Button>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}
