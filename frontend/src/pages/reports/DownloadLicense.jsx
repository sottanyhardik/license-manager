import {useState} from "react";
import {useNavigate} from "react-router-dom";
import api from "../../api/axios";
import {toast} from "react-toastify";

export default function DownloadLicense() {
    const navigate = useNavigate();
    const [licenseStatus, setLicenseStatus] = useState("active");
    const [days, setDays] = useState(365);
    const [loading, setLoading] = useState(false);

    const [bulkInput, setBulkInput] = useState("");
    const [bulkLoading, setBulkLoading] = useState(false);

    const handleDownload = async () => {
        setLoading(true);
        try {
            const url = licenseStatus === "expiring"
                ? `reports/expiring-licenses/?days=${days}`
                : `reports/active-licenses/?days=${days}`;

            const jsonResponse = await api.get(url);
            const licenseNumbers = jsonResponse.data.licenses.map(l => l.license_number);

            if (licenseNumbers.length === 0) {
                toast.error('No licenses found for the selected criteria.');
                return;
            }

            const response = await api.post(
                'licenses/bulk-balance-excel/',
                {license_numbers: licenseNumbers},
                {responseType: 'blob'}
            );

            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(new Blob([response.data]));
            link.setAttribute('download', `licenses_${licenseStatus}_${days}days.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(link.href);
            toast.success(`Downloaded Excel for ${licenseNumbers.length} license(s)`);
        } catch (error) {
            toast.error(error?.response?.data?.error || 'Failed to download. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleBulkDownload = async () => {
        const numbers = bulkInput
            .split(',')
            .map(s => s.trim())
            .filter(Boolean);

        if (numbers.length === 0) {
            toast.error('Please enter at least one license number.');
            return;
        }

        setBulkLoading(true);
        try {
            const response = await api.post(
                'licenses/bulk-balance-excel/',
                {license_numbers: numbers},
                {responseType: 'blob'}
            );

            const link = document.createElement('a');
            link.href = window.URL.createObjectURL(new Blob([response.data]));
            link.setAttribute('download', `bulk_license_summary_${numbers.length}_licenses.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(link.href);
            toast.success(`Downloaded Excel for ${numbers.length} license(s)`);
        } catch (error) {
            const msg = error?.response?.data?.error || 'Failed to download. Please try again.';
            toast.error(msg);
        } finally {
            setBulkLoading(false);
        }
    };

    const parsedCount = bulkInput
        .split(',')
        .map(s => s.trim())
        .filter(Boolean).length;

    return (
        <div style={{ minHeight: '100vh' }}>
            {/* Tabler-style page header */}
            <div className="page-header">
                <div style={{ minWidth: 0 }}>
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span style={{ margin: '0 6px', opacity: 0.5 }}>/</span>
                        Reports
                        <span style={{ margin: '0 6px', opacity: 0.5 }}>/</span>
                        Download License
                    </div>
                    <h1>Download License</h1>
                </div>
            </div>

            <div className="row g-3">
                {/* Bulk Download by License Numbers */}
                <div className="col-md-6">
                    <div className="surface-card h-100">
                        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--tb-border)' }}>
                            <h5 className="mb-0" style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                                <i className="bi bi-upc-scan me-2" style={{ color: 'var(--primary-color)' }}></i>
                                Download by License Numbers
                            </h5>
                        </div>
                        <div className="d-flex flex-column" style={{ padding: '14px 16px' }}>
                            <p className="text-muted small mb-3">
                                Enter DFIA license numbers separated by commas. Each license will get its own sheet in the downloaded Excel file.
                            </p>

                            <div className="mb-3 flex-grow-1">
                                <label className="form-label fw-medium">
                                    License Numbers
                                    {parsedCount > 0 && (
                                        <span className="badge bg-primary ms-2">{parsedCount} entered</span>
                                    )}
                                </label>
                                <textarea
                                    className="form-control font-monospace"
                                    rows={5}
                                    placeholder="e.g. 3011007415, 3011007018, 3011008321"
                                    value={bulkInput}
                                    onChange={(e) => setBulkInput(e.target.value)}
                                />
                                <small className="form-text text-muted">
                                    Comma-separated. Each license = one sheet named after the license number.
                                </small>
                            </div>

                            <button
                                className="btn btn-primary w-100"
                                onClick={handleBulkDownload}
                                disabled={bulkLoading || parsedCount === 0}
                            >
                                {bulkLoading ? (
                                    <>
                                        <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <i className="bi bi-file-earmark-excel me-2"></i>
                                        Download Excel ({parsedCount} license{parsedCount !== 1 ? 's' : ''})
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Download by Status */}
                <div className="col-md-6">
                    <div className="surface-card h-100">
                        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--tb-border)' }}>
                            <h5 className="mb-0" style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                                <i className="bi bi-funnel me-2" style={{ color: 'var(--success-color, #16a34a)' }}></i>
                                Download by Status
                            </h5>
                        </div>
                        <div className="d-flex flex-column" style={{ padding: '14px 16px' }}>
                            <p className="text-muted small mb-3">
                                Export all active or expiring licenses filtered by date range.
                            </p>

                            <div className="mb-3">
                                <label className="form-label fw-medium">License Status</label>
                                <div className="d-flex gap-2 flex-wrap">
                                    {[
                                        {value: "active", label: "Active Licenses", icon: "check-circle-fill", color: "success"},
                                        {value: "expiring", label: "Expiring Soon", icon: "exclamation-triangle-fill", color: "warning"},
                                    ].map(opt => (
                                        <div
                                            key={opt.value}
                                            className={`card flex-fill cursor-pointer ${licenseStatus === opt.value ? `border-${opt.color} bg-${opt.color} bg-opacity-10` : 'border'}`}
                                            style={{cursor: 'pointer', minWidth: '140px'}}
                                            onClick={() => setLicenseStatus(opt.value)}
                                        >
                                            <div className="card-body py-2 px-3 d-flex align-items-center gap-2">
                                                <i className={`bi bi-${opt.icon} text-${opt.color}`}></i>
                                                <span className="small fw-medium">{opt.label}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            <div className="mb-4">
                                <label htmlFor="days" className="form-label fw-medium">
                                    {licenseStatus === "expiring" ? "Expiring within (days)" : "Look-back period (days)"}
                                </label>
                                <input
                                    type="number"
                                    id="days"
                                    className="form-control"
                                    value={days}
                                    onChange={(e) => setDays(parseInt(e.target.value) || 365)}
                                    min="1"
                                    max="3650"
                                />
                                <small className="form-text text-muted">
                                    {licenseStatus === "expiring"
                                        ? `Licenses expiring within the next ${days} days`
                                        : `Active licenses from ${days} days ago through future dates`}
                                </small>
                            </div>

                            <button
                                className="btn btn-success w-100 mt-auto"
                                onClick={handleDownload}
                                disabled={loading}
                            >
                                {loading ? (
                                    <>
                                        <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <i className="bi bi-file-earmark-excel me-2"></i>
                                        Download Excel
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>

                {/* Info card */}
                <div className="col-12">
                    <div className="surface-card">
                        <div style={{ padding: '14px 16px' }}>
                            <h6 className="mb-2" style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                                <i className="bi bi-info-circle me-2" style={{ color: 'var(--primary-color)' }}></i>
                                Excel Report Includes
                            </h6>
                            <div className="row row-cols-2 row-cols-md-3 g-2">
                                {[
                                    "License number, date, expiry, exporter",
                                    "BOE & Allotment summary per license",
                                    "Balance quantity per item (HSN, description)",
                                    "Restriction percentage and CIF values",
                                    "Unit price and CIF FC calculations",
                                    "Each license in its own named sheet",
                                ].map((f, i) => (
                                    <div key={i} className="col">
                                        <span className="small">
                                            <i className="bi bi-check-circle-fill text-success me-1"></i>{f}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
