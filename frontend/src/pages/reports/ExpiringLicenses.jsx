import {useState} from "react";
import api from "../../api/axios";

export default function ExpiringLicenses() {
    const [days, setDays] = useState(30);
    const [loading, setLoading] = useState(false);

    const handleExport = async () => {
        setLoading(true);
        try {
            const response = await api.get(
                `license/reports/expiring-licenses/?format=excel&days=${days}`,
                {
                    responseType: 'blob',
                }
            );

            // Create download link
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `expiring_licenses_${days}_days.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error downloading report:', error);
            alert('Failed to download report. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="container-fluid">
            <div className="row mb-4">
                <div className="col-12">
                    <h2>Expiring Licenses Report</h2>
                    <p className="text-muted">
                        Export licenses expiring within the specified number of days
                    </p>
                </div>
            </div>

            <div className="row">
                <div className="col-md-6">
                    <div className="card">
                        <div className="card-body">
                            <h5 className="card-title">Export Settings</h5>

                            <div className="mb-3">
                                <label htmlFor="days" className="form-label">
                                    Days from today
                                </label>
                                <input
                                    type="number"
                                    id="days"
                                    className="form-control"
                                    value={days}
                                    onChange={(e) => setDays(parseInt(e.target.value) || 30)}
                                    min="1"
                                    max="365"
                                />
                                <small className="form-text text-muted">
                                    Licenses expiring between today and {days} days from now
                                </small>
                            </div>

                            <button
                                className="btn btn-primary"
                                onClick={handleExport}
                                disabled={loading}
                            >
                                {loading ? (
                                    <>
                                        <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <i className="bi bi-download me-2"></i>
                                        Download Excel Report
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    <div className="card mt-3">
                        <div className="card-body">
                            <h6 className="card-title">Report Features</h6>
                            <ul className="list-unstyled mb-0">
                                <li className="mb-2">
                                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                                    Separate sheets for each SION norm
                                </li>
                                <li className="mb-2">
                                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                                    Items grouped by FK with merged serial numbers
                                </li>
                                <li className="mb-2">
                                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                                    Condition notes displayed below items
                                </li>
                                <li className="mb-2">
                                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                                    Item-wise summary per norm
                                </li>
                                <li className="mb-2">
                                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                                    Filtered by purchase status (GE, MI, IP, SM)
                                </li>
                                <li className="mb-2">
                                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                                    Excludes licenses with balance &lt; 100
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
