import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { describeLoadError } from "./errors";

interface LoadErrorPanelProps {
  title: string;
  error: unknown;
  onRetry: () => void;
  compact?: boolean;
}

/** Failed-load state with a Retry action. role="alert" so assistive tech announces it. */
export default function LoadErrorPanel({ title, error, onRetry, compact = false }: LoadErrorPanelProps) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-sm sm:flex-row sm:items-center sm:justify-between",
        compact && "py-3",
      )}
    >
      <div className="space-y-1">
        <p className="font-medium text-destructive">{title}</p>
        <p className="text-muted-foreground">{describeLoadError(error)}</p>
      </div>
      <Button variant="outline" size="sm" onClick={onRetry}>
        Retry
      </Button>
    </div>
  );
}
