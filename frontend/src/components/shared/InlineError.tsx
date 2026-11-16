import { AlertCircleIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { getErrorMessage } from "@/utils/errorUtils";

export interface InlineErrorProps {
    error: unknown;
    onRetry?: () => void;
    title?: string;
}

export function InlineError({ error, onRetry, title = "Something went wrong" }: InlineErrorProps) {
    return (
        <Alert variant="destructive">
            <AlertCircleIcon aria-hidden="true" />
            <AlertTitle>{title}</AlertTitle>
            <AlertDescription>
                <p>{error ? (getErrorMessage(error) as string) : "An unexpected error occurred"}</p>
                {onRetry && (
                    <Button type="button" size="sm" variant="outline" className="mt-2" onClick={onRetry}>
                        Retry
                    </Button>
                )}
            </AlertDescription>
        </Alert>
    );
}
