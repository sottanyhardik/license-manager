import { useCallback, useContext, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AuthContext } from "@/context/AuthContext";
import { cn } from "@/lib/utils";
import { ActionMenu, type ActionMenuItem } from "@/components/shared/ActionMenu";

export interface WorkspaceTab {
    id: string;
    label: string;
    count?: number;
    anyRole?: string[];
    /** Lazy: only the active tab renders. */
    render: () => ReactNode;
}

export interface ModuleWorkspaceProps {
    title: string;
    breadcrumbs?: { label: string; to?: string }[];
    meta?: ReactNode;
    /** At most one. */
    primaryAction?: ReactNode;
    secondaryActions?: ActionMenuItem[];
    kpis?: ReactNode;
    tabs?: WorkspaceTab[];
    defaultTab?: string;
    children?: ReactNode;
}

/** `?tab=` state (replace:true, other params preserved). Unknown/forbidden ids fall back to the default. */
export function useWorkspaceTab(tabs: WorkspaceTab[], defaultId?: string): [string, (id: string) => void] {
    const { hasAnyRole } = useContext(AuthContext);
    const [params, setParams] = useSearchParams();
    const allowed = tabs.filter((t) => !t.anyRole || hasAnyRole(t.anyRole));
    const fallback = allowed.find((t) => t.id === defaultId)?.id ?? allowed[0]?.id ?? "";
    const requested = params.get("tab");
    const active = allowed.some((t) => t.id === requested) ? (requested as string) : fallback;

    const set = useCallback((id: string) => {
        setParams((prev) => {
            const next = new URLSearchParams(prev);
            next.set("tab", id);
            return next;
        }, { replace: true });
    }, [setParams]);

    return [active, set];
}

type HeaderProps = Pick<ModuleWorkspaceProps, "title" | "breadcrumbs" | "meta" | "primaryAction" | "secondaryActions">;

function Header({ title, breadcrumbs, meta, primaryAction, secondaryActions }: HeaderProps) {
    return (
        <header className="space-y-2">
            {breadcrumbs && breadcrumbs.length > 0 && (
                <nav aria-label="Breadcrumb">
                    <ol className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                        {breadcrumbs.map((b, i) => {
                            const last = i === breadcrumbs.length - 1;
                            return (
                                <li key={`${b.label}-${i}`} className="flex items-center gap-1">
                                    {b.to && !last
                                        ? <Link to={b.to} className="hover:text-foreground hover:underline">{b.label}</Link>
                                        : <span aria-current={last ? "page" : undefined}>{b.label}</span>}
                                    {!last && <span aria-hidden="true">/</span>}
                                </li>
                            );
                        })}
                    </ol>
                </nav>
            )}
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <h1 className="text-xl font-semibold text-foreground">{title}</h1>
                    {meta}
                </div>
                <div className="flex items-center gap-2">
                    {secondaryActions && secondaryActions.length > 0 && (
                        <ActionMenu items={secondaryActions} label={`More actions for ${title}`} trigger="button" />
                    )}
                    {primaryAction}
                </div>
            </div>
        </header>
    );
}

export function ModuleWorkspace({ tabs, defaultTab, children, kpis, ...header }: ModuleWorkspaceProps) {
    const { hasAnyRole } = useContext(AuthContext);
    const [active, setActive] = useWorkspaceTab(tabs ?? [], defaultTab);
    const allowed = (tabs ?? []).filter((t) => !t.anyRole || hasAnyRole(t.anyRole));

    return (
        <div className="space-y-4">
            <Header {...header} />
            {kpis && <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">{kpis}</div>}
            {tabs ? (
                <Tabs value={active} onValueChange={setActive}>
                    <TabsList className="sticky top-0 z-10 h-auto max-w-full flex-wrap justify-start">
                        {allowed.map((t) => (
                            <TabsTrigger key={t.id} value={t.id}>
                                {t.label}
                                {t.count !== undefined && (
                                    <span className="rounded bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">{t.count}</span>
                                )}
                            </TabsTrigger>
                        ))}
                    </TabsList>
                    {allowed.map((t) => (
                        <TabsContent key={t.id} value={t.id} className="mt-3 scroll-mt-16">
                            {t.id === active ? t.render() : null}
                        </TabsContent>
                    ))}
                </Tabs>
            ) : children}
        </div>
    );
}

export interface WorkspaceSectionProps {
    title: string;
    description?: string;
    actions?: ReactNode;
    children: ReactNode;
    className?: string;
}

/** Titled, non-collapsible section (collapsible grouping is ModuleAccordion). */
export function WorkspaceSection({ title, description, actions, children, className }: WorkspaceSectionProps) {
    return (
        <section className={cn("space-y-3", className)}>
            <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                    <h2 className="text-base font-semibold text-foreground">{title}</h2>
                    {description && <p className="text-sm text-muted-foreground">{description}</p>}
                </div>
                {actions}
            </div>
            {children}
        </section>
    );
}

export interface DataWorkspaceProps {
    toolbar: ReactNode;
    table: ReactNode;
    pagination?: ReactNode;
}

/** Layout only: toolbar / table / pagination. */
export function DataWorkspace({ toolbar, table, pagination }: DataWorkspaceProps) {
    return (
        <div className="space-y-3">
            <div>{toolbar}</div>
            <div>{table}</div>
            {pagination && <div>{pagination}</div>}
        </div>
    );
}
