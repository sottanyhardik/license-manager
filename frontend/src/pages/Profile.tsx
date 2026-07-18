import { useContext, useEffect, useMemo, useState, type ChangeEvent } from "react";
import { Pencil, Check, AlertCircle, CheckCircle2, X } from "lucide-react";

import { AuthContext } from "../context/AuthContext";
import api from "../api/axios";
import type { AuthUser } from "../types";
import { ROLE_LABELS } from "../utils/roleConstants";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type ProfileFormData = {
    first_name: string;
    last_name: string;
    email: string;
};

type ProfilePayload = {
    first_name: string;
    last_name: string;
    email: string | null;
};

const PROFILE_NAME_LIMITS = {
    first_name: 30,
    last_name: 150,
};

function getProfileFormData(user: AuthUser | null): ProfileFormData {
    return {
        first_name: user?.first_name ?? "",
        last_name: user?.last_name ?? "",
        email: user?.email ?? "",
    };
}

export function buildProfilePayload(formData: ProfileFormData): ProfilePayload {
    const email = formData.email.trim();

    return {
        first_name: formData.first_name.trim(),
        last_name: formData.last_name.trim(),
        email: email || null,
    };
}

function getFieldError(data: unknown, field: string): string | null {
    if (!data || typeof data !== "object" || !(field in data)) {
        return null;
    }

    const value = (data as Record<string, unknown>)[field];
    if (typeof value === "string") {
        return value.trim() || null;
    }
    if (Array.isArray(value)) {
        return value.find((item): item is string => typeof item === "string" && item.trim().length > 0)?.trim() ?? null;
    }

    return null;
}

export function getProfileErrorMessage(error: unknown): string {
    const data = error && typeof error === "object" && "response" in error
        ? (error as { response?: { data?: unknown } }).response?.data
        : null;

    if (data && typeof data === "object") {
        const detail = getFieldError(data, "detail");
        if (detail) return detail;

        const fieldError = ["email", "first_name", "last_name", "non_field_errors"]
            .map((field) => getFieldError(data, field))
            .find((message): message is string => Boolean(message));
        if (fieldError) return fieldError;
    }

    if (error instanceof Error && error.message.trim()) {
        return error.message.trim();
    }

    return "Failed to update profile.";
}

export function normalizeProfileRoles(roles: unknown): string[] {
    if (!Array.isArray(roles)) {
        return [];
    }

    return Array.from(
        new Set(
            roles
                .filter((role): role is string => typeof role === "string")
                .map((role) => role.trim())
                .filter(Boolean),
        ),
    );
}

export default function Profile() {
    const { user, updateUser } = useContext(AuthContext);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string>("");
    const [success, setSuccess] = useState<string>("");
    const [formData, setFormData] = useState<ProfileFormData>(() => getProfileFormData(user));

    useEffect(() => {
        if (!editing) {
            setFormData(getProfileFormData(user));
        }
    }, [editing, user]);

    const roles = useMemo(() => normalizeProfileRoles(user?.roles), [user?.roles]);

    const handleEdit = () => { setEditing(true); setError(""); setSuccess(""); };
    const handleCancel = () => {
        setEditing(false);
        setFormData(getProfileFormData(user));
        setError(""); setSuccess("");
    };
    const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
        const { name, value } = event.target;
        if (!(name in formData)) return;
        setFormData((current) => ({ ...current, [name]: value }));
    };

    const handleSave = async () => {
        setSaving(true);
        setError(""); setSuccess("");
        try {
            const { data } = await api.patch<AuthUser>("/auth/me/", buildProfilePayload(formData));
            updateUser(data);
            setFormData(getProfileFormData(data));
            setSuccess("Profile updated successfully.");
            setEditing(false);
        } catch (err) {
            setError(getProfileErrorMessage(err));
        } finally {
            setSaving(false);
        }
    };

    if (!user) {
        return (
            <div className="py-10 text-center text-sm text-muted-foreground">Loading…</div>
        );
    }

    const initials = ((user.first_name?.[0] || "") + (user.last_name?.[0] || "") || user.username?.[0] || "?").toUpperCase();
    const displayName = user.first_name || user.last_name
        ? `${user.first_name || ""} ${user.last_name || ""}`.trim()
        : user.username;

    const ReadField = ({ value }: { value: string | null | undefined }) => (
        <div className={`flex h-9 items-center rounded-md border border-input bg-muted px-3 text-sm ${value ? "text-foreground" : "text-muted-foreground/60"}`}>
            {value || "Not set"}
        </div>
    );

    return (
        <>
            <PageHeader
                pretitle="Account"
                title="Profile"
                description="Manage your personal information and account settings"
                actions={
                    !editing && (
                        <Button variant="outline" onClick={handleEdit}>
                            <Pencil className="size-4" />
                            Edit Profile
                        </Button>
                    )
                }
            />

            {error && (
                <div role="alert" className="mb-4 flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                    <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
                    <span className="flex-1">{error}</span>
                    <button
                        type="button"
                        onClick={() => setError("")}
                        aria-label="Dismiss error"
                        className="cursor-pointer rounded opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive/50"
                    >
                        <X className="size-4" aria-hidden="true" />
                    </button>
                </div>
            )}
            {success && (
                <div role="status" className="mb-4 flex items-center gap-2.5 rounded-lg border border-success/30 bg-success/10 px-3.5 py-2.5 text-[13px] text-success">
                    <CheckCircle2 className="size-4 shrink-0" aria-hidden="true" />
                    <span className="flex-1">{success}</span>
                    <button
                        type="button"
                        onClick={() => setSuccess("")}
                        aria-label="Dismiss"
                        className="cursor-pointer rounded opacity-70 transition-opacity hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-success/50"
                    >
                        <X className="size-4" aria-hidden="true" />
                    </button>
                </div>
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
                {/* Avatar card */}
                <Card>
                    <CardContent className="flex flex-col items-center pt-6 text-center">
                        <div
                            className="mb-3.5 flex size-18 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/70 text-2xl font-bold tracking-tight text-white shadow-lg"
                            aria-hidden="true"
                        >
                            {initials}
                        </div>
                        <div className="text-[15px] font-semibold tracking-tight text-foreground">
                            {displayName}
                        </div>
                        <div className="mb-3 text-xs text-muted-foreground">@{user.username}</div>
                        <div className="flex flex-wrap justify-center gap-1.5">
                            <Badge variant="success">Active</Badge>
                            {user.is_superuser && <Badge>Superuser</Badge>}
                        </div>
                    </CardContent>
                </Card>

                {/* Details */}
                <div className="flex flex-col gap-4">
                    <Card>
                        <CardHeader className="border-b">
                            <div className="flex items-center justify-between">
                                <CardTitle className="text-sm">Account Details</CardTitle>
                                {editing && <Badge variant="default">Editing</Badge>}
                            </div>
                        </CardHeader>
                        <CardContent className="pt-5">
                            <div className="mb-5">
                                <Label className="mb-1.5" htmlFor="username">Username</Label>
                                <Input id="username" value={user.username} disabled readOnly />
                                <p className="mt-1.5 text-[11.5px] text-muted-foreground">Username cannot be changed.</p>
                            </div>

                            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                                <div>
                                    <Label className="mb-1.5" htmlFor="first_name">First Name</Label>
                                    {editing
                                        ? <Input id="first_name" name="first_name" value={formData.first_name} onChange={handleChange} placeholder="First name" maxLength={PROFILE_NAME_LIMITS.first_name} autoComplete="given-name" />
                                        : <ReadField value={user.first_name} />}
                                </div>
                                <div>
                                    <Label className="mb-1.5" htmlFor="last_name">Last Name</Label>
                                    {editing
                                        ? <Input id="last_name" name="last_name" value={formData.last_name} onChange={handleChange} placeholder="Last name" maxLength={PROFILE_NAME_LIMITS.last_name} autoComplete="family-name" />
                                        : <ReadField value={user.last_name} />}
                                </div>
                                <div className="sm:col-span-2">
                                    <Label className="mb-1.5" htmlFor="email">Email Address</Label>
                                    {editing
                                        ? <Input id="email" type="email" name="email" value={formData.email} onChange={handleChange} placeholder="email@example.com" autoComplete="email" />
                                        : <ReadField value={user.email} />}
                                </div>
                            </div>

                            {editing && (
                                <div className="mt-5 flex gap-2 border-t border-border/70 pt-4">
                                    <Button onClick={handleSave} disabled={saving}>
                                        <Check className="size-4" />
                                        {saving ? "Saving…" : "Save Changes"}
                                    </Button>
                                    <Button variant="outline" onClick={handleCancel} disabled={saving}>
                                        Cancel
                                    </Button>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {roles.length > 0 && (
                        <Card>
                            <CardHeader className="border-b">
                                <CardTitle className="text-sm">Assigned Roles</CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                <div className="flex flex-wrap gap-1.5">
                                    {roles.map((role) => (
                                        <Badge
                                            key={role}
                                            variant="default"
                                            title={role}
                                        >
                                            {ROLE_LABELS[role as keyof typeof ROLE_LABELS] ?? role}
                                        </Badge>
                                    ))}
                                </div>
                            </CardContent>
                        </Card>
                    )}
                </div>
            </div>
        </>
    );
}
