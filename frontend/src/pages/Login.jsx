import {useContext, useEffect, useState} from "react";
import {useNavigate} from "react-router-dom";
import api from "../api/axios";
import {AuthContext} from "../context/AuthContext";

export default function Login() {
    const {user, loading: authLoading, loginSuccess} = useContext(AuthContext);
    const navigate = useNavigate();
    const [form, setForm] = useState({username: "", password: ""});
    const [error, setError] = useState("");
    const [submitting, setSubmitting] = useState(false);

    // Redirect if already logged in
    useEffect(() => {
        if (!authLoading && user) {
            navigate("/dashboard");
        }
    }, [user, authLoading, navigate]);

    const submit = async (e) => {
        e.preventDefault();
        setError("");
        setSubmitting(true);

        try {
            const {data} = await api.post("/auth/login/", form);

            // IMPORTANT: Save access + refresh + user
            loginSuccess({
                access: data.access,
                refresh: data.refresh,
                user: data.user
            });

            // Use React Router navigation instead of page reload
            navigate("/dashboard");
        } catch (e) {
            setError(e.response?.data?.detail || "Invalid username or password");
            setSubmitting(false);
        }
    };

    return (
        <div className="container mt-5" style={{maxWidth: "400px"}}>
            <div className="card p-4 shadow">
                <h3 className="mb-3 text-center">Login</h3>

                {error && (
                    <div className="alert alert-danger" role="alert">
                        {error}
                    </div>
                )}

                <form onSubmit={submit}>
                    <input
                        className="form-control mb-3"
                        placeholder="Username"
                        value={form.username}
                        onChange={(e) =>
                            setForm({...form, username: e.target.value})
                        }
                        required
                    />

                    <input
                        type="password"
                        className="form-control mb-3"
                        placeholder="Password"
                        value={form.password}
                        onChange={(e) =>
                            setForm({...form, password: e.target.value})
                        }
                        required
                    />

                    <button className="btn btn-primary w-100" disabled={submitting}>
                        {submitting ? "Logging in..." : "Login"}
                    </button>
                </form>
            </div>
        </div>
    );
}
