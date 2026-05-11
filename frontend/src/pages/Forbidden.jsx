import {Link} from "react-router-dom";

export default function Forbidden() {
    return (
        <div className="d-flex flex-column align-items-center justify-content-center min-vh-100 text-center p-4">
            <div className="mb-4" style={{fontSize: '4rem'}}>🔒</div>
            <h1 className="h2 fw-bold text-danger mb-2">Access Denied</h1>
            <p className="text-muted mb-4">
                You don't have permission to view this page.
                <br/>
                Contact your administrator if you believe this is an error.
            </p>
            <Link to="/dashboard" className="btn btn-primary">
                Back to Dashboard
            </Link>
        </div>
    );
}
