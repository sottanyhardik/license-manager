import React, { useState, useEffect } from "react";
import { Card, Row, Col, Spinner } from "react-bootstrap";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
    Filler
} from "chart.js";
import { Bar, Pie, Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
    Filler
);

const Dashboard = () => {
  const [lastUpdated, setLastUpdated] = useState(new Date());
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Auto-update timestamp every 10 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setIsRefreshing(true);
      setTimeout(() => {
        setLastUpdated(new Date());
        setIsRefreshing(false);
      }, 1000); // simulate data refresh delay
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (date) => {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  };

  const stats = [
    { title: "Total Licenses", value: 42, icon: "bi-card-checklist", color: "#0d6efd" },
    { title: "Active Trades", value: 18, icon: "bi-graph-up", color: "#28a745" },
    { title: "Pending Allotments", value: 7, icon: "bi-clock-history", color: "#ffc107" },
    { title: "Registered Companies", value: 15, icon: "bi-building", color: "#6f42c1" },
  ];

  const barData = {
    labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    datasets: [
      {
        label: "Licenses Issued",
        backgroundColor: "#0d6efd",
        borderRadius: 6,
        data: [12, 19, 8, 15, 11, 14],
      },
      {
        label: "Allotments Made",
        backgroundColor: "#ff7b00",
        borderRadius: 6,
        data: [8, 15, 6, 10, 7, 9],
      },
    ],
  };

  const pieData = {
    labels: ["Exports", "Imports", "Domestic"],
    datasets: [
      {
        data: [45, 35, 20],
        backgroundColor: ["#0d6efd", "#ff7b00", "#28a745"],
        borderWidth: 0,
      },
    ],
  };

  const lineData = {
    labels: ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
    datasets: [
      {
        label: "Trade Volume (in Cr)",
        data: [200, 250, 210, 320, 280, 360],
        fill: true,
        borderColor: "#6f42c1",
        backgroundColor: "rgba(111, 66, 193, 0.1)",
        tension: 0.3,
        pointBackgroundColor: "#6f42c1",
      },
    ],
  };

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <h2 className="fw-bold text-secondary mb-0">📊 Business Dashboard Overview</h2>

        {/* Last Updated Section */}
        <div className="text-muted small d-flex align-items-center">
          {isRefreshing ? (
            <>
              <Spinner
                animation="border"
                size="sm"
                variant="primary"
                className="me-2"
              />
              <span>Refreshing...</span>
            </>
          ) : (
            <>
              <i className="bi bi-clock-history text-primary me-1"></i>
              Last Updated: <strong className="ms-1">{formatTime(lastUpdated)}</strong>
            </>
          )}
        </div>
      </div>

      {/* Stats Summary Cards */}
      <Row xs={1} md={2} lg={4} className="g-4 mb-4">
        {stats.map((stat, idx) => (
          <Col key={idx}>
            <Card className="text-center shadow-sm border-0">
              <Card.Body>
                <div
                  className="rounded-circle mb-3"
                  style={{
                    width: "50px",
                    height: "50px",
                    margin: "0 auto",
                    backgroundColor: stat.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "white",
                  }}
                >
                  <i className={`bi ${stat.icon} fs-5`}></i>
                </div>
                <h6 className="fw-semibold text-muted">{stat.title}</h6>
                <h3 className="fw-bold text-dark">{stat.value}</h3>
              </Card.Body>
            </Card>
          </Col>
        ))}
      </Row>

      {/* Charts Section */}
      <Row className="g-4">
        <Col md={6}>
          <Card className="shadow-sm border-0">
            <Card.Body>
              <Card.Title className="mb-3 fw-semibold text-secondary">
                License vs Allotments
              </Card.Title>
              <Bar
                data={barData}
                options={{ responsive: true, plugins: { legend: { position: "bottom" } } }}
              />
            </Card.Body>
          </Card>
        </Col>

        <Col md={6}>
          <Card className="shadow-sm border-0">
            <Card.Body>
              <Card.Title className="mb-3 fw-semibold text-secondary">
                Trade Distribution
              </Card.Title>
              <div style={{ maxWidth: "320px", margin: "0 auto" }}>
                <Pie
                  data={pieData}
                  options={{ plugins: { legend: { position: "bottom" } } }}
                />
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="g-4 mt-4">
        <Col>
          <Card className="shadow-sm border-0">
            <Card.Body>
              <Card.Title className="mb-3 fw-semibold text-secondary">
                Monthly Trade Volume
              </Card.Title>
              <Line
                data={lineData}
                options={{ responsive: true, plugins: { legend: { position: "bottom" } } }}
              />
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  );
};

export default Dashboard;
