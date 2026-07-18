import { useCallback, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Pencil, Trash2, Search, Users } from "lucide-react";

import { deleteUser, listUsers } from "../../api/users";
import { AuthContext } from "../../context/AuthContext";
import { getErrorMessage } from "../../utils/errorUtils";
import { ROLE_LABELS, ROLE_BADGE_COLOR, ROLE_BADGE_STYLE } from "../../utils/roleConstants";
import EmptyState from "@/components/EmptyState";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import {
    Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";

interface UserRecord {
    id: number;
    username: string;
    email?: string;
    first_name?: string;
    last_name?: string;
    is_active: boolean;
    is_superuser?: boolean;
    is_staff?: boolean;
    roles?: string[];
    date_joined?: string;
}

const BOOTSTRAP_TO_BADGE: Record<string, "default" | "secondary" | "destructive" | "success" | "warning" | "info"> = {
    primary: "default", success: "success", danger: "destructive",
    warning: "warning", info: "info", secondary: "secondary", dark: "secondary",
};

export default function UserList() {
    const navigate = useNavigate();
    const { user: currentUser } = useContext(AuthContext);

    const [users, setUsers] = useState<UserRecord[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState("");
    const [roleFilter, setRoleFilter] = useState("");
    const [activeFilter, setActiveFilter] = useState("");
    const [confirmDelete, setConfirmDelete] = useState<UserRecord | null>(null);

    const fetchUsers = useCallback(async () => {
        setLoading(true);
        try {
            const params: Record<string, string> = {};
            if (search) params.search = search;
            if (roleFilter) params.role = roleFilter;
            if (activeFilter !== "") params.is_active = activeFilter;
            const { data } = await listUsers(params);
            setUsers(Array.isArray(data) ? data : data.results ?? []);
        } catch (err: unknown) {
            toast.error(getErrorMessage(err as Error));
        } finally {
            setLoading(false);
        }
    }, [search, roleFilter, activeFilter]);

    useEffect(() => { fetchUsers(); }, [fetchUsers]);

    const handleDelete = async (userId: number) => {
        try {
            await deleteUser(userId);
            toast.success("User deleted");
            setConfirmDelete(null);
            fetchUsers();
        } catch (err: unknown) {
            toast.error(getErrorMessage(err as Error));
        }
    };

    // Select uses non-empty sentinel values; map to "" for the API
    const ALL = "__all__";

    return (
        <>
            <PageHeader
                pretitle="Admin"
                title="User Management"
                description="Manage users, roles and access"
                actions={
                    <Button onClick={() => navigate("/admin/users/create")}>
                        <Plus className="size-4" />
                        Add User
                    </Button>
                }
            />

            {/* Filters */}
            <Card className="mb-3">
                <CardContent className="flex flex-wrap items-center gap-2 py-3">
                    <div className="relative min-w-[220px] flex-1">
                        <Search className="absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                        <Input
                            className="h-9 pl-8"
                            placeholder="Search by username or email…"
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                    <Select value={roleFilter || ALL} onValueChange={(v) => setRoleFilter(v === ALL ? "" : v)}>
                        <SelectTrigger className="w-[200px]"><SelectValue placeholder="All Roles" /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ALL}>All Roles</SelectItem>
                            {Object.keys(ROLE_LABELS).map((code) => (
                                <SelectItem key={code} value={code}>{ROLE_LABELS[code]}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    <Select value={activeFilter || ALL} onValueChange={(v) => setActiveFilter(v === ALL ? "" : v)}>
                        <SelectTrigger className="w-[140px]"><SelectValue placeholder="All Status" /></SelectTrigger>
                        <SelectContent>
                            <SelectItem value={ALL}>All Status</SelectItem>
                            <SelectItem value="true">Active</SelectItem>
                            <SelectItem value="false">Inactive</SelectItem>
                        </SelectContent>
                    </Select>
                </CardContent>
            </Card>

            {/* Table */}
            <Card>
                <CardContent className="p-0">
                    {loading ? (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                        <th scope="col" className="px-4 py-2.5">User</th>
                                        <th scope="col" className="px-4 py-2.5">Email</th>
                                        <th scope="col" className="px-4 py-2.5">Roles</th>
                                        <th scope="col" className="px-4 py-2.5">Status</th>
                                        <th scope="col" className="px-4 py-2.5 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {[...Array(5)].map((_, i) => (
                                        <tr key={i} className="border-b border-border/60">
                                            <td className="px-4 py-2.5"><Skeleton className="h-4 w-28" /></td>
                                            <td className="px-4 py-2.5"><Skeleton className="h-3 w-36" /></td>
                                            <td className="px-4 py-2.5"><Skeleton className="h-4 w-20 rounded-full" /></td>
                                            <td className="px-4 py-2.5"><Skeleton className="h-4 w-14 rounded-full" /></td>
                                            <td className="px-4 py-2.5"><div className="flex justify-end gap-1.5"><Skeleton className="h-7 w-16 rounded-md" /><Skeleton className="size-7 rounded-md" /></div></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : users.length === 0 ? (
                        <EmptyState
                            icon={Users}
                            title="No users found"
                            description="Try adjusting the filters or add a new user"
                            action={<Button size="sm" onClick={() => navigate("/admin/users/create")}><Plus className="size-4" />Add User</Button>}
                        />
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                        <th scope="col" className="px-4 py-2.5">User</th>
                                        <th scope="col" className="px-4 py-2.5">Email</th>
                                        <th scope="col" className="px-4 py-2.5">Roles</th>
                                        <th scope="col" className="px-4 py-2.5">Status</th>
                                        <th scope="col" className="px-4 py-2.5 text-right">Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map((u) => (
                                        <tr key={u.id} className="border-b border-border/60 transition-colors hover:bg-accent/40">
                                            <td className="px-4 py-2.5">
                                                <div className="flex items-center gap-1.5 font-medium text-foreground">
                                                    {u.username}
                                                    {u.is_superuser && <Badge variant="destructive">Super Admin</Badge>}
                                                </div>
                                                {(u.first_name || u.last_name) && (
                                                    <div className="text-xs text-muted-foreground">{u.first_name} {u.last_name}</div>
                                                )}
                                            </td>
                                            <td className="px-4 py-2.5 text-muted-foreground">{u.email || "—"}</td>
                                            <td className="px-4 py-2.5">
                                                {(u.roles ?? []).length === 0 ? (
                                                    <span className="text-xs text-muted-foreground">No roles</span>
                                                ) : (
                                                    <div className="flex flex-wrap gap-1">
                                                        {(u.roles ?? []).map((r) => {
                                                            const customStyle = ROLE_BADGE_STYLE?.[r as keyof typeof ROLE_BADGE_STYLE];
                                                            const bootstrapColor = ROLE_BADGE_COLOR?.[r as keyof typeof ROLE_BADGE_COLOR];
                                                            const label = ROLE_LABELS[r as keyof typeof ROLE_LABELS] ?? r;
                                                            if (customStyle) {
                                                                return (
                                                                    <span key={r} className="inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium" style={customStyle}>
                                                                        {label}
                                                                    </span>
                                                                );
                                                            }
                                                            const variant = BOOTSTRAP_TO_BADGE[bootstrapColor ?? "secondary"] ?? "secondary";
                                                            return <Badge key={r} variant={variant} className="text-[10px]">{label}</Badge>;
                                                        })}
                                                    </div>
                                                )}
                                            </td>
                                            <td className="px-4 py-2.5">
                                                <Badge variant={u.is_active ? "success" : "secondary"}>
                                                    {u.is_active ? "Active" : "Inactive"}
                                                </Badge>
                                            </td>
                                            <td className="px-4 py-2.5">
                                                <div className="flex justify-end gap-1.5">
                                                    <Button variant="outline" size="sm" onClick={() => navigate(`/admin/users/${u.id}/edit`)}>
                                                        <Pencil className="size-3.5" />
                                                        Edit
                                                    </Button>
                                                    {currentUser?.is_superuser && u.id !== currentUser?.id && (
                                                        <Button variant="outline" size="sm" className="text-destructive hover:bg-destructive/10" onClick={() => setConfirmDelete(u)}>
                                                            <Trash2 className="size-3.5" />
                                                        </Button>
                                                    )}
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Delete confirmation */}
            <Dialog open={!!confirmDelete} onOpenChange={(o) => !o && setConfirmDelete(null)}>
                <DialogContent className="max-w-sm">
                    <DialogHeader>
                        <DialogTitle>Delete User</DialogTitle>
                        <DialogDescription>
                            Are you sure you want to delete <strong className="text-foreground">{confirmDelete?.username}</strong>? This cannot be undone.
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setConfirmDelete(null)}>Cancel</Button>
                        <Button variant="destructive" onClick={() => handleDelete(confirmDelete.id)}>Delete</Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
