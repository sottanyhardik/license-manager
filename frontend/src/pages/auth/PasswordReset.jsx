import {useContext, useState} from "react";
import api from "../../api/axios";
import {ToastContext} from "../../components/ToastContext";

export default function PasswordReset() {
    const {showToast} = useContext(ToastContext);
    const [email, setEmail] = useState("");

    const submit = async (e) => {
        e.preventDefault();
        try {
            await api.post("/auth/password-reset/", {email});
            showToast("Reset instructions sent to your email.");
        } catch {
            showToast("Error sending reset email", "danger");
        }
    };

    return (
        <div className="container mt-5" style={{maxWidth: "400px"}}>
            <div className="card p-4 shadow">
                <h3 className="mb-3 text-center">Forgot Password</h3>

                <form onSubmit={submit}>
                    <div className="mb-3">
                        <label className="form-label">Email address</label>
                        <input
                            type="email"
                            className="form-control"
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </div>

                    <button className="btn btn-primary w-100">Send Reset Email</button>
                </form>
            </div>
        </div>
    );
}
