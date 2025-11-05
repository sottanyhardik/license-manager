import React, { useEffect, useState, useContext } from "react";
import { Form, Button, Card } from "react-bootstrap";
import { ToastContext } from "../context/ToastContext";
import api from "../api/axios";

const Profile = () => {
  const { showToast } = useContext(ToastContext);
  const [user, setUser] = useState({});
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("accounts/auth/me/")
      .then((res) => setUser(res.data))
      .catch(() => showToast("Failed to load profile", "info"))
      .finally(() => setLoading(false));
  }, [showToast]);

  const handleSave = async () => {
    try {
      await api.put("accounts/auth/me/", user);
      showToast("Profile updated successfully!", "success");
      setIsEditing(false);
    } catch {
      showToast("Error saving profile", "danger");
    }
  };

  if (loading) {
    return (
      <div className="text-center py-5 text-muted">
        <div className="spinner-border text-warning mb-3"></div>
        <p>Loading profile...</p>
      </div>
    );
  }

  return (
    <Card className="shadow-sm border-0">
      <Card.Body>
        <Card.Title className="fw-bold text-secondary mb-4">👤 My Profile</Card.Title>
        <Form>
          {["first_name", "last_name", "email"].map((field) => (
            <Form.Group className="mb-3" key={field}>
              <Form.Label>{field.replace("_", " ").replace(/\b\w/g, (c) => c.toUpperCase())}</Form.Label>
              <Form.Control
                type={field === "email" ? "email" : "text"}
                value={user[field] || ""}
                disabled={!isEditing}
                onChange={(e) => setUser({ ...user, [field]: e.target.value })}
              />
            </Form.Group>
          ))}
          {!isEditing ? (
            <Button className="btn-orange" onClick={() => setIsEditing(true)}>
              Edit Profile
            </Button>
          ) : (
            <div className="d-flex gap-2">
              <Button variant="success" onClick={handleSave}>Save Changes</Button>
              <Button variant="secondary" onClick={() => setIsEditing(false)}>Cancel</Button>
            </div>
          )}
        </Form>
      </Card.Body>
    </Card>
  );
};

export default Profile;
