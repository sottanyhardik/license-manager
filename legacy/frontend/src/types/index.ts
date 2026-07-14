// ── Auth ──────────────────────────────────────────────────────────────────────
export interface AuthUser {
    id: number;
    username: string;
    first_name: string;
    last_name: string;
    email: string;
    is_superuser: boolean;
    is_staff: boolean;
    is_active: boolean;
    roles: string[];
    date_joined: string;
}

export interface LoginResponse {
    access: string;
    refresh: string;
    user: AuthUser;
}

export interface AuthContextValue {
    user: AuthUser | null;
    loading: boolean;
    loginSuccess: (data: LoginResponse) => void;
    logout: (reason?: string) => Promise<void>;
    hasRole: (roleCode: string) => boolean;
    hasAnyRole: (roleCodes: string[]) => boolean;
    isSuperAdmin: () => boolean;
    canManageUsers: () => boolean;
}

// ── Common API shapes ─────────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
    count: number;
    next: string | null;
    previous: string | null;
    results: T[];
}

// ── Masters ───────────────────────────────────────────────────────────────────
export interface FieldMeta {
    type?: string;
    label?: string;
    required?: boolean;
    read_only?: boolean;
    endpoint?: string;
    fk_endpoint?: string;
    label_field?: string;
    value_field?: string;
    choices?: Array<[string, string] | { value: string; label: string }>;
    max_length?: number;
    help_text?: string;
    widget?: string;
    many?: boolean;
}

export interface FieldDefinition extends FieldMeta {
    name: string;
    grid?: string;
}

export interface NestedFieldDef {
    field_name: string;
    fields: FieldDefinition[];
    label?: string;
    min_rows?: number;
}

export type FormData = Record<string, unknown>;

// ── Domain entities (minimal — extend as needed) ──────────────────────────────
export interface License {
    id: number;
    license_number: string;
    license_type: string;
    exporter?: string;
    status?: string;
    expiry_date?: string | null;
    [key: string]: unknown;
}

export interface Trade {
    id: number;
    reference_number?: string;
    direction: 'PURCHASE' | 'SALE';
    status?: string;
    [key: string]: unknown;
}

// ── UI helpers ────────────────────────────────────────────────────────────────
export type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';

export interface SelectOption {
    value: string | number;
    label: string;
}

export interface ChipDef {
    icon?: string;
    label: string;
    tone?: Tone;
    style?: React.CSSProperties;
}

export interface ActionDef {
    icon?: string;
    title?: string;
    label?: string;
    tone?: Tone;
    onClick: (item?: unknown) => void;
    disabled?: boolean;
    hidden?: boolean;
}

export interface SummaryItem {
    label: string;
    value: React.ReactNode;
    tone?: Tone;
}
