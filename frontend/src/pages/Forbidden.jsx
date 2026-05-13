import { Link } from "react-router-dom";
import { Button, EmptyState } from "../components/ui";

export default function Forbidden() {
    return (
        <div
            className="d-flex align-items-center justify-content-center"
            style={{ minHeight: "100vh", background: "var(--tb-body-bg)", padding: 20 }}
        >
            <div className="card" style={{ maxWidth: 480, width: "100%" }}>
                <div className="card-body">
                    <EmptyState
                        icon="lock"
                        title="Access denied"
                        description="You don't have permission to view this page. Contact your administrator if you believe this is an error."
                        action={
                            <Link to="/dashboard">
                                <Button variant="primary" size="sm" icon="house">Back to Dashboard</Button>
                            </Link>
                        }
                    />
                </div>
            </div>
        </div>
    );
}
