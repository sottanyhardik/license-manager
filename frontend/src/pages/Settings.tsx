import { useContext, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { toast } from "sonner";
import api from "../api/axios";
import { AuthContext } from "../context/AuthContext";
import { ROLE_LABELS, ROLE_BADGE_COLOR, ROLE_BADGE_STYLE } from "../utils/roleConstants";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
    Dialog, DialogContent,
    DialogFooter, DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import EmptyState from "@/components/EmptyState";
import { cn } from "@/lib/utils";
import {
    Check, Lock, Pencil, Plus, ShieldCheck, SquarePen,
    ToggleRight, Trash2, User, UserPlus, Users, X,
} from "lucide-react";
import MdsStatusCard from "./settings/MdsStatusCard";

// ─── Types ───────────────────────────────────────────────────────────────────

interface UserRecord {
    id: number;
    username: string;
    email?: string;
    first_name?: string;
    last_name?: string;
    is_active: boolean;
    is_superuser?: boolean;
    roles?: string[];
    date_joined?: string;
}

type FormData = {
    username: string;
    email: string;
    first_name: string;
    last_name: string;
    password: string;
    is_active: boolean;
    roles: string[];
};

// ─── Utilities ───────────────────────────────────────────────────────────────

function fmtDate(val: string | null | undefined): string {
    if (!val) return "—";
    const d = new Date(val);
    if (isNaN(d.getTime())) return "—";
    return `${String(d.getDate()).padStart(2, "0")}-${String(d.getMonth() + 1).padStart(2, "0")}-${d.getFullYear()}`;
}

// ─── Tone → Tailwind class map ────────────────────────────────────────────────

const TONE_CLASSES: Record<string, { wrapper: string; label: string }> = {
    primary: { wrapper: "border-l-primary",           label: "text-primary" },
    success: { wrapper: "border-l-success",           label: "text-success" },
    info:    { wrapper: "border-l-info",              label: "text-info" },
    neutral: { wrapper: "border-l-border",            label: "text-muted-foreground" },
};

// ─── Role badge → shadcn Badge variant map ────────────────────────────────────

type BadgeVariant = "default" | "secondary" | "destructive" | "success" | "warning" | "info" | "outline";

const BOOTSTRAP_TO_BADGE_VARIANT: Record<string, BadgeVariant> = {
    primary:   "default",
    success:   "success",
    danger:    "destructive",
    warning:   "warning",
    info:      "info",
    secondary: "secondary",
    dark:      "secondary",
};

// ─── SectionBox ───────────────────────────────────────────────────────────────

interface SectionBoxProps {
    icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" | "false" }>;
    label: string;
    tone?: "primary" | "success" | "info" | "neutral";
    children: React.ReactNode;
}

function SectionBox({ icon: Icon, label, tone = "primary", children }: SectionBoxProps) {
    const tc = TONE_CLASSES[tone] ?? TONE_CLASSES.primary;
    return (
        <div className={cn(
            "rounded-md border border-border border-l-[3px] bg-card p-4",
            tc.wrapper,
        )}>
            <div className={cn(
                "mb-3 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-[0.08em]",
                tc.label,
            )}>
                {Icon && <Icon className="size-3.5" aria-hidden="true" />}
                {label}
            </div>
            {children}
        </div>
    );
}

// ─── RoleBadge ────────────────────────────────────────────────────────────────

function RoleBadge({ code }: { code: string }) {
    const label = ROLE_LABELS[code as keyof typeof ROLE_LABELS] ?? code;
    const customStyle = ROLE_BADGE_STYLE?.[code as keyof typeof ROLE_BADGE_STYLE];
    const bootstrapColor = ROLE_BADGE_COLOR?.[code as keyof typeof ROLE_BADGE_COLOR];

    if (customStyle) {
        return (
            <span
                className="inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium"
                style={customStyle}
            >
                {label}
            </span>
        );
    }
    const variant = BOOTSTRAP_TO_BADGE_VARIANT[bootstrapColor ?? "secondary"] ?? "secondary";
    return (
        <Badge variant={variant} className="text-[10px]">
            {label}
        </Badge>
    );
}

// ─── Table skeleton ───────────────────────────────────────────────────────────

function TableSkeleton() {
    return (
        <div className="overflow-x-auto">
            <table className="table mb-0">
                <thead>
                    <tr>
                        {["w-36", "w-40", "w-28", "w-32", "w-16", "w-20", "w-16"].map((w, i) => (
                            <th key={i} scope="col">
                                <Skeleton className={`h-3 ${w}`} />
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {[...Array(4)].map((_, ri) => (
                        <tr key={ri}>
                            <td className="pl-4">
                                <div className="flex items-center gap-2.5">
                                    <Skeleton className="size-[30px] rounded-full shrink-0" />
                                    <Skeleton className="h-3 w-24" />
                                </div>
                            </td>
                            <td><Skeleton className="h-3 w-36" /></td>
                            <td><Skeleton className="h-3 w-24" /></td>
                            <td><Skeleton className="h-4 w-20 rounded-full" /></td>
                            <td><Skeleton className="h-4 w-12 rounded-full" /></td>
                            <td><Skeleton className="h-3 w-20" /></td>
                            <td className="pr-4">
                                <div className="flex justify-end gap-1">
                                    <Skeleton className="size-8 rounded-md" />
                                    <Skeleton className="size-8 rounded-md" />
                                </div>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

// ─── Initial form state ───────────────────────────────────────────────────────

const EMPTY_FORM: FormData = {
    username: "", email: "", first_name: "", last_name: "",
    password: "", is_active: true, roles: [],
};

// ─── Main component ───────────────────────────────────────────────────────────

export default function Settings() {
    const { user: currentUser } = useContext(AuthContext);
    const [users, setUsers] = useState<UserRecord[]>([]);
    const [availableRoles, setAvailableRoles] = useState<string[]>([]);
    const [loading, setLoading] = useState(true);
    const [showModal, setShowModal] = useState(false);
    const [editingUser, setEditingUser] = useState<UserRecord | null>(null);
    const [saving, setSaving] = useState(false);
    const [formData, setFormData] = useState<FormData>(EMPTY_FORM);
    const [deleteTarget, setDeleteTarget] = useState<{ id: number; username: string } | null>(null);

    useEffect(() => {
        if (!currentUser?.is_superuser) { setLoading(false); return; }
        loadUsers();
        api.get("auth/users/available-roles/")
            .then(r => setAvailableRoles(r.data))
            .catch(() => {});
    }, [currentUser?.is_superuser]);

    const loadUsers = async () => {
        try {
            const { data } = await api.get("auth/users/");
            setUsers(Array.isArray(data) ? data : data.results ?? []);
        } catch {
            toast.error("Failed to load users");
            setUsers([]);
        } finally {
            setLoading(false);
        }
    };

    const handleOpenModal = (user: UserRecord | null = null) => {
        if (user) {
            setEditingUser(user);
            setFormData({
                username: user.username,
                email: user.email ?? "",
                first_name: user.first_name ?? "",
                last_name: user.last_name ?? "",
                password: "",
                is_active: user.is_active,
                roles: user.roles ?? [],
            });
        } else {
            setEditingUser(null);
            setFormData(EMPTY_FORM);
        }
        setShowModal(true);
    };

    const toggleRole = (code: string) =>
        setFormData(prev => ({
            ...prev,
            roles: prev.roles.includes(code)
                ? prev.roles.filter(r => r !== code)
                : [...prev.roles, code],
        }));

    const handleCloseModal = () => { setShowModal(false); setEditingUser(null); };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        try {
            const payload: Partial<FormData> = { ...formData };
            if (editingUser && !payload.password) delete payload.password;
            if (editingUser) {
                await api.put(`auth/users/${editingUser.id}/`, payload);
                toast.success("User updated");
            } else {
                await api.post("auth/users/", payload);
                toast.success("User created");
            }
            handleCloseModal();
            loadUsers();
        } catch (err: unknown) {
            const msg = (err as { response?: { data?: { detail?: string } } })
                ?.response?.data?.detail;
            toast.error(msg ?? "Failed to save user");
        } finally {
            setSaving(false);
        }
    };

    const handleDeleteConfirmed = async () => {
        if (!deleteTarget) return;
        try {
            await api.delete(`auth/users/${deleteTarget.id}/`);
            toast.success("User deleted");
            loadUsers();
        } catch {
            toast.error("Failed to delete user");
        } finally {
            setDeleteTarget(null);
        }
    };

    if (currentUser && !currentUser.is_superuser) return <Navigate to="/403" replace />;

    return (
        <>
            <PageHeader
                pretitle="Admin"
                title="Users & Roles"
                description="Manage users and assign roles — visible to superusers only"
                actions={
                    <Button size="sm" onClick={() => handleOpenModal()}>
                        <Plus className="size-4" aria-hidden="true" />
                        Add User
                    </Button>
                }
            />

            {/* ── User management card ───────────────────────────────── */}
            <Card>
                <CardHeader className="border-b">
                    <div className="flex items-center gap-2">
                        <Users className="size-4 text-muted-foreground" aria-hidden="true" />
                        <span className="text-[13.5px] font-semibold text-foreground">User Management</span>
                        <Badge variant="default" className="ml-1 text-[10px]">
                            {users.length}
                        </Badge>
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    {loading ? (
                        <TableSkeleton />
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="table table-hover mb-0">
                                <thead>
                                    <tr>
                                        <th scope="col" className="pl-4">User</th>
                                        <th scope="col">Email</th>
                                        <th scope="col">Name</th>
                                        <th scope="col">Roles</th>
                                        <th scope="col">Status</th>
                                        <th scope="col">Joined</th>
                                        <th scope="col" className="text-end pr-4">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(user => (
                                        <tr key={user.id} className="align-top">
                                            {/* Avatar + username */}
                                            <td className="pl-4 pt-3">
                                                <div className="flex items-start gap-2.5">
                                                    <div
                                                        className="mt-0.5 flex size-[30px] shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/70 text-[12px] font-bold text-white"
                                                        aria-hidden="true"
                                                    >
                                                        {user.username[0].toUpperCase()}
                                                    </div>
                                                    <div>
                                                        <div className="text-[13px] font-medium text-foreground">
                                                            {user.username}
                                                        </div>
                                                        {user.is_superuser && (
                                                            <Badge variant="destructive" className="mt-0.5 text-[10px]">
                                                                Superuser
                                                            </Badge>
                                                        )}
                                                    </div>
                                                </div>
                                            </td>

                                            {/* Email */}
                                            <td className="pt-3 text-[12.5px] text-muted-foreground">
                                                {user.email || "—"}
                                            </td>

                                            {/* Name */}
                                            <td className="pt-3 text-[12.5px]">
                                                {user.first_name || user.last_name
                                                    ? `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim()
                                                    : "—"}
                                            </td>

                                            {/* Roles */}
                                            <td className="pt-3">
                                                {(user.roles ?? []).length === 0 ? (
                                                    <span className="text-[12px] text-muted-foreground">—</span>
                                                ) : (
                                                    <div className="flex flex-wrap gap-1">
                                                        {(user.roles ?? []).map(r => (
                                                            <RoleBadge key={r} code={r} />
                                                        ))}
                                                    </div>
                                                )}
                                            </td>

                                            {/* Status */}
                                            <td className="pt-3">
                                                <Badge
                                                    variant={user.is_active ? "success" : "secondary"}
                                                    className="text-[10.5px]"
                                                >
                                                    {user.is_active ? "Active" : "Inactive"}
                                                </Badge>
                                            </td>

                                            {/* Joined date */}
                                            <td className="pt-3 whitespace-nowrap text-[12px] text-muted-foreground">
                                                {fmtDate(user.date_joined)}
                                            </td>

                                            {/* Actions */}
                                            <td className="pr-4 pt-2 text-end">
                                                <div className="inline-flex gap-1">
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => handleOpenModal(user)}
                                                        title="Edit"
                                                        aria-label={`Edit ${user.username}`}
                                                    >
                                                        <Pencil className="size-4" aria-hidden="true" />
                                                    </Button>
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        className="text-destructive hover:bg-destructive/10 hover:border-destructive/30"
                                                        onClick={() => setDeleteTarget({ id: user.id, username: user.username })}
                                                        title="Delete"
                                                        aria-label={`Delete ${user.username}`}
                                                    >
                                                        <Trash2 className="size-4" aria-hidden="true" />
                                                    </Button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}

                                    {/* Empty state */}
                                    {users.length === 0 && (
                                        <tr>
                                            <td colSpan={7}>
                                                <EmptyState
                                                    icon={Users}
                                                    title="No users found"
                                                    description="Add a user to get started"
                                                    action={
                                                        <Button size="sm" onClick={() => handleOpenModal()}>
                                                            <Plus className="size-4" aria-hidden="true" />
                                                            Add User
                                                        </Button>
                                                    }
                                                />
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* ── Master Data Service card ───────────────────────── */}
            <MdsStatusCard />

            {/* ── Delete confirmation ────────────────────────────── */}
            <ConfirmDialog
                show={deleteTarget !== null}
                title="Delete User"
                message={`Are you sure you want to delete "${deleteTarget?.username}"? This action cannot be undone.`}
                severity="danger"
                confirmText="Delete"
                onConfirm={handleDeleteConfirmed}
                onCancel={() => setDeleteTarget(null)}
            />

            {/* ── Add / Edit user dialog ─────────────────────────── */}
            <Dialog open={showModal} onOpenChange={open => { if (!open) handleCloseModal(); }}>
                <DialogContent
                    className="max-w-[640px] p-0 gap-0 overflow-hidden"
                    showCloseButton={false}
                >
                    {/* ── Dialog header ──────────────────────────── */}
                    <div className="flex shrink-0 items-center gap-3 border-b border-border px-5 py-4">
                        <div className="flex size-8 shrink-0 items-center justify-center rounded-md border border-primary/20 bg-primary/10 text-primary">
                            {editingUser
                                ? <SquarePen className="size-4" aria-hidden="true" />
                                : <UserPlus className="size-4" aria-hidden="true" />}
                        </div>
                        <DialogTitle className="text-[15px] font-semibold tracking-tight">
                            {editingUser ? "Edit User" : "Add New User"}
                        </DialogTitle>
                        <button
                            type="button"
                            onClick={handleCloseModal}
                            aria-label="Close dialog"
                            className="ml-auto inline-flex size-7 cursor-pointer items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                            <X className="size-4" aria-hidden="true" />
                            <span className="sr-only">Close</span>
                        </button>
                    </div>

                    {/* ── Form ──────────────────────────────────────── */}
                    <form onSubmit={handleSubmit} className="flex flex-col overflow-hidden">
                        {/* Scrollable body */}
                        <div
                            className="flex flex-col gap-3 overflow-y-auto p-5"
                            style={{ maxHeight: "calc(90vh - 130px)" }}
                        >
                            {/* Account credentials */}
                            <SectionBox icon={Lock} label="Account Credentials" tone="primary">
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                                    <div>
                                        <Label className="mb-1.5" htmlFor="modal-username">
                                            Username <span className="text-destructive" aria-hidden="true">*</span>
                                        </Label>
                                        <Input
                                            id="modal-username"
                                            value={formData.username}
                                            onChange={e => setFormData({ ...formData, username: e.target.value })}
                                            required
                                            disabled={!!editingUser}
                                            placeholder="Enter username"
                                            autoComplete="off"
                                            aria-required="true"
                                        />
                                        {editingUser && (
                                            <p className="mt-1 text-[11.5px] text-muted-foreground">
                                                Username cannot be changed.
                                            </p>
                                        )}
                                    </div>
                                    <div>
                                        <Label className="mb-1.5" htmlFor="modal-password">
                                            Password
                                            {!editingUser && (
                                                <span className="text-destructive" aria-hidden="true"> *</span>
                                            )}
                                        </Label>
                                        <Input
                                            id="modal-password"
                                            type="password"
                                            value={formData.password}
                                            onChange={e => setFormData({ ...formData, password: e.target.value })}
                                            required={!editingUser}
                                            placeholder={editingUser ? "Leave blank to keep current" : "Enter password"}
                                            autoComplete="new-password"
                                            aria-required={!editingUser}
                                        />
                                    </div>
                                </div>
                            </SectionBox>

                            {/* Personal information */}
                            <SectionBox icon={User} label="Personal Information" tone="success">
                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                                    <div>
                                        <Label className="mb-1.5" htmlFor="modal-fname">First Name</Label>
                                        <Input
                                            id="modal-fname"
                                            value={formData.first_name}
                                            onChange={e => setFormData({ ...formData, first_name: e.target.value })}
                                            placeholder="First name"
                                        />
                                    </div>
                                    <div>
                                        <Label className="mb-1.5" htmlFor="modal-lname">Last Name</Label>
                                        <Input
                                            id="modal-lname"
                                            value={formData.last_name}
                                            onChange={e => setFormData({ ...formData, last_name: e.target.value })}
                                            placeholder="Last name"
                                        />
                                    </div>
                                    <div>
                                        <Label className="mb-1.5" htmlFor="modal-email">Email</Label>
                                        <Input
                                            id="modal-email"
                                            type="email"
                                            value={formData.email}
                                            onChange={e => setFormData({ ...formData, email: e.target.value })}
                                            placeholder="email@example.com"
                                        />
                                    </div>
                                </div>
                            </SectionBox>

                            {/* Roles */}
                            {availableRoles.length > 0 && (
                                <SectionBox icon={ShieldCheck} label="Roles" tone="info">
                                    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                                        {availableRoles.map(code => {
                                            const checked = formData.roles.includes(code);
                                            return (
                                                <div
                                                    key={code}
                                                    onClick={() => toggleRole(code)}
                                                    className={cn(
                                                        "flex cursor-pointer items-center gap-2 rounded-md border px-2.5 py-2 transition-all",
                                                        checked
                                                            ? "border-primary/50 bg-primary/10 shadow-sm"
                                                            : "border-border bg-card hover:bg-muted/60",
                                                    )}
                                                >
                                                    <input
                                                        type="checkbox"
                                                        id={`role-${code}`}
                                                        checked={checked}
                                                        onChange={() => toggleRole(code)}
                                                        onClick={e => e.stopPropagation()}
                                                        className="size-4 shrink-0 cursor-pointer rounded accent-primary"
                                                    />
                                                    <label
                                                        htmlFor={`role-${code}`}
                                                        className={cn(
                                                            "cursor-pointer select-none text-[11.5px]",
                                                            checked ? "font-semibold text-primary" : "font-medium text-muted-foreground",
                                                        )}
                                                    >
                                                        {ROLE_LABELS[code as keyof typeof ROLE_LABELS] ?? code}
                                                    </label>
                                                </div>
                                            );
                                        })}
                                    </div>
                                </SectionBox>
                            )}

                            {/* Account status */}
                            <SectionBox icon={ToggleRight} label="Account Status" tone="neutral">
                                <div className="flex items-center gap-3">
                                    <Switch
                                        id="modal-is-active"
                                        checked={formData.is_active}
                                        onCheckedChange={checked => setFormData({ ...formData, is_active: checked })}
                                    />
                                    <Label htmlFor="modal-is-active" className="cursor-pointer text-sm font-normal">
                                        Active — allow this user to log in
                                    </Label>
                                </div>
                            </SectionBox>
                        </div>

                        {/* ── Footer ──────────────────────────────────── */}
                        <DialogFooter className="shrink-0 border-t border-border bg-muted/30 px-5 py-3">
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                onClick={handleCloseModal}
                                disabled={saving}
                            >
                                Cancel
                            </Button>
                            <Button type="submit" size="sm" disabled={saving}>
                                {!saving && (
                                    editingUser
                                        ? <Check className="size-4" aria-hidden="true" />
                                        : <UserPlus className="size-4" aria-hidden="true" />
                                )}
                                {saving ? "Saving…" : editingUser ? "Update User" : "Create User"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </>
    );
}
