import { Link } from "react-router-dom";
import { Button, EmptyState } from "../../components/ui";

export default function ServerError() {
    return (
        <div
            className="d-flex align-items-center justify-content-center"
            style={{ minHeight: "100vh", background: "var(--tb-body-bg)", padding: 20 }}
        >
            <div className="card" style={{ maxWidth: 480, width: "100%" }}>
                <div className="card-body">
                    <EmptyState
                        icon="exclamation-octagon"
                        title="500 — Something went wrong"
                        description="A server error occurred. Please try again in a moment."
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
