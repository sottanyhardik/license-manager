import { Compass, House } from "lucide-react";
import ErrorScreen from "../../components/ErrorScreen";

export default function NotFound() {
    return (
        <ErrorScreen
            code="404"
            icon={Compass}
            tone="muted"
            title="Page not found"
            description="The page you’re looking for doesn’t exist or has been moved."
            action={{ to: "/dashboard", label: "Back to Dashboard", icon: House }}
        />
    );
}
