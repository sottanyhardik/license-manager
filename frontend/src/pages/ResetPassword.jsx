import React, { useState, useContext } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { Card, Button, Form } from "react-bootstrap";
import { ToastContext } from "../context/ToastContext";
import api from "../api/axios";
import "../styles/login.css";

const ResetPassword = () => {
  const { showToast } = useContext(ToastContext);
  const navigate = useNavigate();
  const { uid, token } = useParams();

  const [formData, setFormData] = useState({
    new_password: "",
    confirm_password: "",
  });

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (formData.new_password !== formData.confirm_password) {
      showToast("Passwords do not match!", "danger");
      return;
    }

    try {
      await api.post("accounts/auth/password-reset-confirm/", {
        uid,
        token,
        new_password: formData.new_password,
      });
      showToast("Password has been reset successfully!", "success");
      navigate("/login");
    } catch (error) {
      const msg =
        error.response?.data?.detail ||
        "Invalid or expired reset link. Please try again.";
      showToast(msg, "danger");
    }
  };

  return (
    <div className="login-page d-flex align-items-center justify-content-center vh-100 bg-light">
      <Card className="shadow-sm border-0 login-card">
        <Card.Body>
          <h4 className="text-center mb-4 fw-bold text-secondary">
            🔒 Reset Password
          </h4>

          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>New Password</Form.Label>
              <Form.Control
                type="password"
                value={formData.new_password}
                onChange={(e) =>
                  setFormData({ ...formData, new_password: e.target.value })
                }
                required
              />
            </Form.Group>

            <Form.Group className="mb-4">
              <Form.Label>Confirm Password</Form.Label>
              <Form.Control
                type="password"
                value={formData.confirm_password}
                onChange={(e) =>
                  setFormData({ ...formData, confirm_password: e.target.value })
                }
                required
              />
            </Form.Group>

            <Button type="submit" className="w-100 btn-orange mb-3">
              Reset Password
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

export default ResetPassword;
