import {useContext, useState} from "react";
import {useNavigate} from "react-router-dom";
import api from "../../api/axios";
import {ToastContext} from "../../components/ToastContext";

export default function PasswordReset() {
    const {showToast} = useContext(ToastContext);
    const navigate = useNavigate();
    const [email, setEmail] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [sent, setSent] = useState(false);

    const submit = async (e) => {
        e.preventDefault();
        setSubmitting(true);
        try {
            await api.post("/auth/password-reset/", {email});
            setSent(true);
            showToast("Reset instructions sent to your email.");
        } catch {
            showToast("Error sending reset email", "danger");
        } finally {
            setSubmitting(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)',
            padding: '20px'
        }}>
            <div className="card border-0 shadow-lg" style={{ maxWidth: '420px', width: '100%', borderRadius: '16px', overflow: 'hidden' }}>
                {/* Header */}
                <div style={{
                    background: 'linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)',
                    padding: '36px 32px',
                    textAlign: 'center',
                    color: 'white'
                }}>
                    <div style={{
                        width: '72px', height: '72px', margin: '0 auto 16px',
                        borderRadius: '18px',
                        background: 'rgba(255,255,255,0.2)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        backdropFilter: 'blur(10px)'
                    }}>
                        <i className="bi bi-key" style={{ fontSize: '2rem' }}></i>
                    </div>
                    <h2 style={{ fontSize: '1.6rem', fontWeight: '700', marginBottom: '6px' }}>Forgot Password</h2>
                    <p style={{ fontSize: '0.9rem', opacity: 0.9, marginBottom: 0 }}>
                        Enter your email to receive reset instructions
                    </p>
                </div>

                {/* Body */}
                <div style={{ padding: '32px' }}>
                    {sent ? (
                        <div className="text-center">
                            <div style={{
                                width: 64, height: 64, borderRadius: '50%',
                                background: '#d1fae5',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                margin: '0 auto 16px'
                            }}>
                                <i className="bi bi-check-lg text-success" style={{ fontSize: '1.75rem' }}></i>
                            </div>
                            <h6 className="fw-bold mb-2">Check Your Email</h6>
                            <p className="text-muted small mb-4">
                                Reset instructions have been sent to <strong>{email}</strong>.
                            </p>
                            <button
                                className="btn btn-outline-primary w-100"
                                onClick={() => navigate('/login')}
                                style={{ borderRadius: '10px', padding: '12px' }}
                            >
                                <i className="bi bi-arrow-left me-2"></i>Back to Login
                            </button>
                        </div>
                    ) : (
                        <form onSubmit={submit}>
                            <div className="mb-4">
                                <label className="form-label" style={{ fontWeight: '500', color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: 8 }}>
                                    <i className="bi bi-envelope me-2"></i>Email Address
                                </label>
                                <input
                                    type="email"
                                    className="form-control"
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    placeholder="Enter your email"
                                    required
                                    style={{ padding: '12px 16px', borderRadius: '10px', border: '1px solid #d1d5db', fontSize: '1rem' }}
                                />
                            </div>

                            <button
                                className="btn w-100 mb-3"
                                type="submit"
                                disabled={submitting}
                                style={{
                                    padding: '13px 24px', fontWeight: '600', fontSize: '1rem',
                                    background: 'linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)',
                                    border: 'none', borderRadius: '10px', color: 'white',
                                    boxShadow: '0 4px 12px rgba(79,70,229,0.3)'
                                }}
                            >
                                {submitting ? (
                                    <><span className="spinner-border spinner-border-sm me-2"></span>Sending...</>
                                ) : (
                                    <><i className="bi bi-send me-2"></i>Send Reset Email</>
                                )}
                            </button>

                            <div className="text-center">
                                <button
                                    type="button"
                                    className="btn btn-link text-muted p-0"
                                    style={{ fontSize: '0.875rem', textDecoration: 'none' }}
                                    onClick={() => navigate('/login')}
                                >
                                    <i className="bi bi-arrow-left me-1"></i>Back to Login
                                </button>
                            </div>
                        </form>
                    )}
                </div>

                <div style={{ padding: '16px 32px', backgroundColor: 'var(--bs-gray-50)', textAlign: 'center', borderTop: '1px solid #e5e7eb' }}>
                    <small style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                        License Manager System
                    </small>
                </div>
            </div>
        </div>
    );
}
