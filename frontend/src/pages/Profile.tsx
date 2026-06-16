import { useContext, useState } from "react";
import { Pencil, Check, AlertCircle, CheckCircle2, X } from "lucide-react";

import { AuthContext } from "../context/AuthContext";
import api from "../api/axios";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function Profile() {
    const { user, loginSuccess } = useContext(AuthContext);
    const [editing, setEditing] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [formData, setFormData] = useState({
        first_name: user?.first_name || "",
        last_name: user?.last_name || "",
        email: user?.email || "",
    });

    const handleEdit = () => { setEditing(true); setError(""); setSuccess(""); };
    const handleCancel = () => {
        setEditing(false);
        setFormData({ first_name: user?.first_name || "", last_name: user?.last_name || "", email: user?.email || "" });
        setError(""); setSuccess("");
    };
    const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

    const handleSave = async () => {
        setSaving(true);
        setError(""); setSuccess("");
        try {
            const { data } = await api.patch("/auth/me/", formData);
            loginSuccess({ access: localStorage.getItem("access"), refresh: localStorage.getItem("refresh"), user: data });
            setSuccess("Profile updated successfully.");
            setEditing(false);
        } catch (err) {
            setError(err.response?.data?.detail || err.response?.data?.email?.[0] || "Failed to update profile.");
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

    // Read-only field display
    const ReadField = ({ value }) => (
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
                <div className="mb-4 flex items-center gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                    <AlertCircle className="size-4 shrink-0" />
                    <span className="flex-1">{error}</span>
                    <button onClick={() => setError("")} aria-label="Dismiss" className="cursor-pointer opacity-70 hover:opacity-100">
                        <X className="size-4" />
                    </button>
                </div>
            )}
            {success && (
                <div className="mb-4 flex items-center gap-2.5 rounded-lg border border-success/30 bg-success/10 px-3.5 py-2.5 text-[13px] text-success">
                    <CheckCircle2 className="size-4 shrink-0" />
                    <span>{success}</span>
                </div>
            )}

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-[260px_1fr]">
                {/* Avatar card */}
                <Card>
                    <CardContent className="flex flex-col items-center pt-6 text-center">
                        <div
                            className="mb-3.5 flex size-18 items-center justify-center rounded-full text-2xl font-bold tracking-tight text-white shadow-lg"
                            style={{ background: "linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))" }}
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
                        <CardHeader className="flex-row items-center justify-between border-b">
                            <CardTitle className="text-sm">Account Details</CardTitle>
                            {editing && <Badge>Editing</Badge>}
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
                                        ? <Input id="first_name" name="first_name" value={formData.first_name} onChange={handleChange} placeholder="First name" />
                                        : <ReadField value={user.first_name} />}
                                </div>
                                <div>
                                    <Label className="mb-1.5" htmlFor="last_name">Last Name</Label>
                                    {editing
                                        ? <Input id="last_name" name="last_name" value={formData.last_name} onChange={handleChange} placeholder="Last name" />
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

                    {Array.isArray(user.roles) && user.roles.length > 0 && (
                        <Card>
                            <CardHeader className="border-b">
                                <CardTitle className="text-sm">Assigned Roles</CardTitle>
                            </CardHeader>
                            <CardContent className="pt-4">
                                <div className="flex flex-wrap gap-1.5">
                                    {user.roles.map((role) => (
                                        <span
                                            key={role}
                                            className="rounded-md border border-primary/15 bg-primary/10 px-2 py-1 font-mono text-[11.5px] font-medium text-primary"
                                        >
                                            {role}
                                        </span>
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
