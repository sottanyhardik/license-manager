import { Link } from "react-router-dom";
import { Button, EmptyState } from "../../components/ui";

export default function Unauthorized() {
    return (
        <div
            className="d-flex align-items-center justify-content-center"
            style={{ minHeight: "100vh", background: "var(--tb-body-bg)", padding: 20 }}
        >
            <div className="card" style={{ maxWidth: 480, width: "100%" }}>
                <div className="card-body">
                    <EmptyState
                        icon="shield-lock"
                        title="401 — Not authorized"
                        description="You need to sign in to view this page."
                        action={
                            <Link to="/login">
                                <Button variant="primary" size="sm" icon="box-arrow-in-right">
                                    Sign in
                                </Button>
                            </Link>
                        }
                    />
                </div>
            </div>
        </div>
    );
}
