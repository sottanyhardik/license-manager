import React, { useState, useContext } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Card, Button, Form } from "react-bootstrap";
import { ToastContext } from "../context/ToastContext";
import api from "../api/axios";
import "../styles/login.css";

const ForgotPassword = () => {
  const { showToast } = useContext(ToastContext);
  const [username, setUsername] = useState("");
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.post("accounts/auth/password-reset/", { username });
      showToast("Password reset link sent to your registered email!", "success");
      navigate("/login");
    } catch (error) {
      const msg =
        error.response?.data?.detail || "Error sending reset link. Try again.";
      showToast(msg, "danger");
    }
  };

  return (
    <div className="login-page d-flex align-items-center justify-content-center vh-100 bg-light">
      <Card className="shadow-sm border-0 login-card">
        <Card.Body>
          <h4 className="text-center mb-4 fw-bold text-secondary">
            🔁 Forgot Password
          </h4>

          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-4">
              <Form.Label>Username</Form.Label>
              <Form.Control
                type="text"
                placeholder="Enter your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </Form.Group>

            <Button type="submit" className="w-100 btn-orange mb-3">
              Send Reset Link
            </Button>

            <div className="text-center">
              <Link to="/login" className="text-orange">
                Back to Login
              </Link>
            </div>
          </Form>
        </Card.Body>
      </Card>
    </div>
  );
};

export default ForgotPassword;
