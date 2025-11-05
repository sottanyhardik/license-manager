import React, { useState, useContext } from "react";
import { useNavigate, Link } from "react-router-dom";
import { Card, Button, Form } from "react-bootstrap";
import { ToastContext } from "../context/ToastContext";
import { AuthContext } from "../context/AuthContext";
import api from "../api/axios";
import "../styles/login.css";

const Login = () => {
  const { showToast } = useContext(ToastContext);
  const { login } = useContext(AuthContext);
  const navigate = useNavigate();
  const [credentials, setCredentials] = useState({ username: "", password: "" });

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("accounts/auth/login/", credentials);

      localStorage.setItem("access", data.access);
      localStorage.setItem("refresh", data.refresh);
      localStorage.setItem("user", JSON.stringify(data.user));

      login(data.user);
      showToast("Login successful!", "success");
      navigate("/dashboard", { replace: true });
    } catch (error) {
      const msg = error.response?.data?.detail || "Invalid credentials.";
      showToast(msg, "danger");
    }
  };

  return (
    <div className="login-page d-flex align-items-center justify-content-center vh-100 bg-light">
      <Card className="shadow-sm border-0 login-card">
        <Card.Body>
          <h4 className="text-center mb-4 fw-bold text-secondary">🔐 Login</h4>

          <Form onSubmit={handleSubmit}>
            <Form.Group className="mb-3">
              <Form.Label>Username</Form.Label>
              <Form.Control
                type="text"
                name="username"
                value={credentials.username}
                onChange={(e) =>
                  setCredentials({ ...credentials, username: e.target.value })
                }
                required
              />
            </Form.Group>

            <Form.Group className="mb-4">
              <Form.Label>Password</Form.Label>
              <Form.Control
                type="password"
                name="password"
                value={credentials.password}
                onChange={(e) =>
                  setCredentials({ ...credentials, password: e.target.value })
                }
                required
              />
            </Form.Group>

            <Button type="submit" className="w-100 btn-orange mb-3">
              Login
            </Button>

            <div className="text-center">
              <Link to="/forgot-password" className="text-orange">
                Forgot Password?
              </Link>
            </div>
          </Form>
        </Card.Body>
      </Card>
    </div>
  );
};

export default Login;
