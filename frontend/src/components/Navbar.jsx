import React, { useContext } from "react";
import { Navbar, Nav, Dropdown } from "react-bootstrap";
import { Link, useNavigate } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";

const TopNavbar = () => {
  const navigate = useNavigate();
  const { user, logout, timeLeft } = useContext(AuthContext);

  const minutes = Math.floor(timeLeft / 60);
  const seconds = timeLeft % 60;

  if (!user) return null;

  return (
    <Navbar expand="lg" className="navbar-custom px-4 py-2 shadow-sm">
      <Navbar.Brand
        as={Link}
        to="/dashboard"
        className="text-light fw-bold"
        style={{ textDecoration: "none" }}
      >
        <i className="bi bi-gear me-2"></i>License Manager
      </Navbar.Brand>

      <Nav className="ms-auto d-flex align-items-center">
        <div className="text-light small me-4">
          <i className="bi bi-stopwatch me-1 text-warning"></i>
          <strong>{minutes}m {seconds}s</strong> left
        </div>

        <Dropdown align="end">
          <Dropdown.Toggle
            variant="outline-light"
            id="dropdown-profile"
            className="d-flex align-items-center border-light"
          >
            <i className="bi bi-person-circle me-2"></i>
            {user.username}
          </Dropdown.Toggle>

          <Dropdown.Menu className="shadow border-0">
            <Dropdown.Item
              className="text-orange fw-semibold"
              onClick={() => navigate("/profile")}
            >
              <i className="bi bi-pencil-square me-2 text-orange"></i>Edit Profile
            </Dropdown.Item>

            <Dropdown.Item
              className="text-orange fw-semibold"
              onClick={() => navigate("/dashboard")}
            >
              <i className="bi bi-house-door me-2 text-orange"></i>Dashboard
            </Dropdown.Item>

            <Dropdown.Divider />

            <Dropdown.Item
              className="text-orange fw-semibold"
              onClick={logout}
            >
              <i className="bi bi-box-arrow-right me-2 text-orange"></i>Logout
            </Dropdown.Item>
          </Dropdown.Menu>
        </Dropdown>
      </Nav>
    </Navbar>
  );
};

export default TopNavbar;
