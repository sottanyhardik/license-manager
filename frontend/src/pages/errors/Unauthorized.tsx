import { LockKeyhole, LogIn } from "lucide-react";
import ErrorScreen from "../../components/ErrorScreen";

export default function Unauthorized() {
    return (
        <ErrorScreen
            code="401"
            icon={LockKeyhole}
            tone="warning"
            title="Not authorized"
            description="You need to sign in to view this page."
            action={{ to: "/login", label: "Sign in", icon: LogIn }}
        />
    );
}
