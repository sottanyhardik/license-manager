import {useNavigate} from "react-router-dom";

export default function Settings() {
  const navigate = useNavigate();

  return (
    <div className="container mt-4">
      {/* Breadcrumb */}
      <nav aria-label="breadcrumb" className="mb-3">
        <ol className="breadcrumb">
          <li className="breadcrumb-item">
            <a href="/" onClick={(e) => { e.preventDefault(); navigate('/'); }}>Home</a>
          </li>
          <li className="breadcrumb-item active" aria-current="page">Settings</li>
        </ol>
      </nav>

      <h1>Settings (Admin Only)</h1>
    </div>
  );
}
