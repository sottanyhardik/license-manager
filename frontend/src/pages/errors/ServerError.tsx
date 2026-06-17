import { ServerCrash, House, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import ErrorScreen from "../../components/ErrorScreen";

export default function ServerError() {
    return (
        <ErrorScreen
            code="500"
            icon={ServerCrash}
            tone="destructive"
            title="Something went wrong"
            description="A server error occurred. Please try refreshing, or come back in a moment."
            action={{ to: "/dashboard", label: "Back to Dashboard", icon: House }}
            secondary={
                <Button variant="outline" onClick={() => window.location.reload()}>
                    <RefreshCw className="size-4" />
                    Retry
                </Button>
            }
        />
    );
}
