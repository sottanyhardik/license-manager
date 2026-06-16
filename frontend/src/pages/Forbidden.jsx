import { ShieldX, House } from "lucide-react";
import ErrorScreen from "../components/ErrorScreen";

export default function Forbidden() {
    return (
        <ErrorScreen
            code="403"
            icon={ShieldX}
            tone="destructive"
            title="Access denied"
            description="You don’t have permission to view this page. Contact your administrator if you believe this is an error."
            action={{ to: "/dashboard", label: "Back to Dashboard", icon: House }}
        />
    );
}
