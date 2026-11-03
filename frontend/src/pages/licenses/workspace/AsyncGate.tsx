import type { ReactNode } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import LoadErrorPanel from "@/pages/licence-balances/LoadErrorPanel";

interface AsyncGateProps<T> {
  data: T | undefined;
  isError: boolean;
  error: unknown;
  onRetry: () => void;
  loadingLabel: string;
  errorTitle: string;
  children: (data: T) => ReactNode;
}

/**
 * Loading, error and ready states for one tab's data. Errors use the shared
 * LoadErrorPanel (role="alert" with a Retry button), which maps 401 and 403 to
 * plain sentences instead of raw server text.
 */
export default function AsyncGate<T>({ data, isError, error, onRetry, loadingLabel, errorTitle, children }: AsyncGateProps<T>) {
  if (data !== undefined) return children(data);
  if (isError) return <LoadErrorPanel title={errorTitle} error={error} onRetry={onRetry} />;
  return (
    <div role="status" aria-live="polite" aria-label={loadingLabel} className="flex flex-col gap-3">
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-40 w-full" />
    </div>
  );
}

/** Ready state with no rows. Plain text, announced politely. */
export function EmptyPanel({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed bg-card p-6 text-center text-sm text-muted-foreground">{children}</div>
  );
}
