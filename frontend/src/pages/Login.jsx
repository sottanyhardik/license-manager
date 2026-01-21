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
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            padding: '20px'
        }}>
            <div className="card border-0 shadow-lg" style={{
                maxWidth: '440px',
                width: '100%',
                borderRadius: '16px',
                overflow: 'hidden'
            }}>
                {/* Header Section */}
                <div style={{
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    padding: '40px 32px',
                    textAlign: 'center',
                    color: 'white'
                }}>
                    <div style={{
                        width: '80px',
                        height: '80px',
                        margin: '0 auto 20px',
                        borderRadius: '20px',
                        background: 'rgba(255, 255, 255, 0.2)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        backdropFilter: 'blur(10px)'
                    }}>
                        <i className="bi bi-shield-check" style={{ fontSize: '2.5rem' }}></i>
                    </div>
                    <h2 style={{ fontSize: '1.75rem', fontWeight: '700', marginBottom: '8px' }}>
                        Welcome Back
                    </h2>
                    <p style={{ fontSize: '1rem', opacity: '0.95', marginBottom: '0' }}>
                        License Manager System
                    </p>
                </div>

                {/* Form Section */}
                <div style={{ padding: '40px 32px' }}>
                    {error && (
                        <div className="alert alert-danger d-flex align-items-center" role="alert" style={{
                            borderRadius: '10px',
                            marginBottom: '24px'
                        }}>
                            <i className="bi bi-exclamation-circle-fill me-2"></i>
                            {error}
                        </div>
                    )}

                    <form onSubmit={submit}>
                        <div className="mb-3">
                            <label className="form-label" style={{
                                fontWeight: '500',
                                color: '#374151',
                                marginBottom: '8px',
                                fontSize: '0.875rem'
                            }}>
                                <i className="bi bi-person me-2"></i>
                                Username
                            </label>
                            <input
                                className="form-control"
                                placeholder="Enter your username"
                                value={form.username}
                                onChange={(e) =>
                                    setForm({...form, username: e.target.value})
                                }
                                required
                                style={{
                                    padding: '12px 16px',
                                    borderRadius: '10px',
                                    border: '1px solid #d1d5db',
                                    fontSize: '1rem'
                                }}
                            />
                        </div>

                        <div className="mb-4">
                            <label className="form-label" style={{
                                fontWeight: '500',
                                color: '#374151',
                                marginBottom: '8px',
                                fontSize: '0.875rem'
                            }}>
                                <i className="bi bi-lock me-2"></i>
                                Password
                            </label>
                            <input
                                type="password"
                                className="form-control"
                                placeholder="Enter your password"
                                value={form.password}
                                onChange={(e) =>
                                    setForm({...form, password: e.target.value})
                                }
                                required
                                style={{
                                    padding: '12px 16px',
                                    borderRadius: '10px',
                                    border: '1px solid #d1d5db',
                                    fontSize: '1rem'
                                }}
                            />
                        </div>

                        <button
                            className="btn w-100"
                            disabled={submitting}
                            style={{
                                padding: '14px 24px',
                                fontWeight: '600',
                                fontSize: '1rem',
                                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                border: 'none',
                                borderRadius: '10px',
                                color: 'white',
                                boxShadow: '0 4px 12px rgba(102, 126, 234, 0.3)'
                            }}
                        >
                            {submitting ? (
                                <>
                                    <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                    Logging in...
                                </>
                            ) : (
                                <>
                                    <i className="bi bi-box-arrow-in-right me-2"></i>
                                    Login
                                </>
                            )}
                        </button>
                    </form>
                </div>

                {/* Footer */}
                <div style={{
                    padding: '24px 32px',
                    backgroundColor: '#f8f9fa',
                    textAlign: 'center',
                    borderTop: '1px solid #e5e7eb'
                }}>
                    <small style={{ color: '#6b7280', fontSize: '0.85rem' }}>
                        Made with <span style={{color: '#dc3545'}}>❤️</span> by Hardik Sottany
                    </small>
                </div>
            </div>
        </div>
    );
}
