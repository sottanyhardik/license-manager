import { Link } from "react-router-dom";
import { Button, EmptyState } from "../../components/ui";

export default function NotFound() {
    return (
        <div
            className="d-flex align-items-center justify-content-center"
            style={{ minHeight: "100vh", background: "var(--tb-body-bg)", padding: 20 }}
        >
            <div className="card" style={{ maxWidth: 480, width: "100%" }}>
                <div className="card-body">
                    <EmptyState
                        icon="signpost-split"
                        title="404 — Page not found"
                        description="The page you're looking for doesn't exist or has been moved."
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
