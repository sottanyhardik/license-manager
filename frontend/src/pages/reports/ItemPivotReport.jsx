import React, {useState, useEffect} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";
import api from "../../api/axios";

export default function ItemPivotReport() {
    const [reportData, setReportData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);

    // Filter states
    const [selectedCompanies, setSelectedCompanies] = useState([]);
    const [excludeCompanies, setExcludeCompanies] = useState([]);
    const [sionNorms, setSionNorms] = useState([]);
    const [filtersCollapsed, setFiltersCollapsed] = useState(false);
    const [activeNormTab, setActiveNormTab] = useState(null);
    const [availableNorms, setAvailableNorms] = useState([]);

    useEffect(() => {
        loadFilterOptions();
        loadAvailableNorms();
    }, []);

    // Load report when active norm tab changes
    useEffect(() => {
        if (activeNormTab) {
            loadReport(activeNormTab);
        }
    }, [activeNormTab, selectedCompanies, excludeCompanies]);

    const loadFilterOptions = async () => {
        try {
            // Load SION norms (only active ones)
            const normsResponse = await api.get('masters/sion-classes/?is_active=true');
            const normsData = normsResponse.data?.results || normsResponse.data || [];
            setSionNorms(Array.isArray(normsData) ? normsData : []);
        } catch (error) {
            console.error('Error loading filter options:', error);
            setSionNorms([]);
        }
    };

    const loadAvailableNorms = async () => {
        try {
            // Fetch all norms that have licenses with balance > 100
            let url = 'license/reports/item-pivot/?format=json&days=30';
            console.log('Fetching available norms from:', url);
            const response = await api.get(url);
            console.log('Available norms response:', response.data);
            const norms = Object.keys(response.data.licenses_by_norm_notification || {}).sort();
            console.log('Extracted norms:', norms);
            setAvailableNorms(norms);

            // Set first norm as active
            if (norms.length > 0 && !activeNormTab) {
                console.log('Setting active norm to:', norms[0]);
                setActiveNormTab(norms[0]);
            }
        } catch (error) {
            console.error('Error loading available norms:', error);
            setAvailableNorms([]);
        }
    };

    const loadReport = async (normClass) => {
        if (!normClass) return;

        setLoading(true);
        try {
            let url = `license/reports/item-pivot/?format=json&days=30&sion_norm=${normClass}`;

            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }

            console.log('Fetching report for norm:', normClass, 'URL:', url);
            const response = await api.get(url);
            console.log('Report data received:', response.data);
            setReportData(response.data);
        } catch (error) {
            console.error('Error loading report:', error);
            alert('Failed to load report. Please try again.');
            setReportData(null);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async () => {
        setDownloading(true);
        try {
            let url = `license/reports/item-pivot/?format=excel&days=30`;

            if (activeNormTab) {
                url += `&sion_norm=${activeNormTab}`;
            }
            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            
            const response = await api.get(url, {
                responseType: 'blob',
            });

            const downloadUrl = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = downloadUrl;
            link.setAttribute('download', `item_pivot_report.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(downloadUrl);
        } catch (error) {
            console.error('Error downloading report:', error);
            alert('Failed to download report. Please try again.');
        } finally {
            setDownloading(false);
        }
    };

    const handleCompanyChange = (values) => {
        setSelectedCompanies(values || []);
    };

    const handleExcludeCompanyChange = (values) => {
        setExcludeCompanies(values || []);
    };

    const handleClearFilters = () => {
        setSelectedCompanies([]);
        setExcludeCompanies([]);
    };

    const hasActiveFilters = selectedCompanies.length > 0 || excludeCompanies.length > 0;

    const getTotalLicenseCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            Object.values(notifications).forEach(licenses => {
                total += licenses.length;
            });
        });
        return total;
    };

    const getTotalNotificationCount = () => {
        if (!reportData) return 0;
        let total = 0;
        Object.values(reportData.licenses_by_norm_notification || {}).forEach(notifications => {
            total += Object.keys(notifications).length;
        });
        return total;
    };

    if (loading) {
        return (
            <div className="container-fluid">
                <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
                    <div className="text-center">
                        <div className="spinner-border text-primary mb-3" role="status" style={{ width: '3rem', height: '3rem' }}>
                            <span className="visually-hidden">Loading...</span>
                        </div>
                        <h5 className="text-muted">Loading Item Pivot Report...</h5>
                        <p className="text-muted small">Please wait while we fetch the data</p>
                    </div>
                </div>
            </div>
        );
    }

    if (!reportData && !loading && activeNormTab) {
        return (
            <div className="container-fluid py-5">
                <div className="alert alert-info d-flex align-items-center" role="alert">
                    <i className="bi bi-info-circle-fill me-3" style={{ fontSize: '1.5rem' }}></i>
                    <div>
                        <h5 className="alert-heading mb-1">No Report Data Available</h5>
                        <p className="mb-0">No licenses found for norm: {activeNormTab}. Try adjusting your filters or check back later.</p>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="container-fluid py-3" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh' }}>
            {/* Header Section */}
            <div className="row mb-4">
                <div className="col-12">
                    <div className="card shadow-sm border-0">
                        <div className="card-body">
                            <div className="d-flex justify-content-between align-items-center flex-wrap">
                                <div className="mb-2 mb-md-0">
                                    <h2 className="mb-1">
                                        <i className="bi bi-table me-2 text-primary"></i>
                                        Item Pivot Report
                                    </h2>
                                    <p className="text-muted mb-0 small">
                                        {reportData && (
                                            <>
                                                <i className="bi bi-calendar-event me-1"></i>
                                                Report Date: {reportData.report_date}
                                                <span className="mx-2">•</span>
                                            </>
                                        )}
                                        <i className="bi bi-tag-fill me-1"></i>
                                        Active Norm: {activeNormTab || 'Loading...'}
                                        {reportData && (
                                            <>
                                                <span className="mx-2">•</span>
                                                <i className="bi bi-bell me-1"></i>
                                                {getTotalNotificationCount()} Notifications
                                                <span className="mx-2">•</span>
                                                <i className="bi bi-file-text me-1"></i>
                                                {getTotalLicenseCount()} Licenses
                                            </>
                                        )}
                                    </p>
                                </div>
                                <div className="d-flex gap-2">
                                    <button
                                        className="btn btn-outline-primary"
                                        onClick={() => setFiltersCollapsed(!filtersCollapsed)}
                                    >
                                        <i className={`bi bi-funnel${hasActiveFilters ? '-fill' : ''} me-2`}></i>
                                        {filtersCollapsed ? 'Show' : 'Hide'} Filters
                                        {hasActiveFilters && <span className="badge bg-primary ms-2">Active</span>}
                                    </button>
                                    <button
                                        className="btn btn-success"
                                        onClick={handleExport}
                                        disabled={downloading}
                                    >
                                        {downloading ? (
                                            <>
                                                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
                                                Downloading...
                                            </>
                                        ) : (
                                            <>
                                                <i className="bi bi-file-earmark-excel me-2"></i>
                                                Export to Excel
                                            </>
                                        )}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Filters Section */}
            {!filtersCollapsed && (
                <div className="row mb-4">
                    <div className="col-12">
                        <div className="card shadow-sm border-0">
                            <div className="card-header bg-white border-bottom">
                                <h5 className="mb-0">
                                    <i className="bi bi-sliders me-2"></i>
                                    Filters
                                </h5>
                            </div>
                            <div className="card-body">
                                <div className="row g-3">
                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">
                                            <i className="bi bi-building me-1"></i>
                                            Include Companies
                                        </label>
                                        <AsyncSelectField
                                            endpoint="masters/companies/"
                                            labelField="name"
                                            valueField="id"
                                            value={selectedCompanies}
                                            onChange={handleCompanyChange}
                                            isMulti={true}
                                            placeholder="Select companies..."
                                            loadOnMount={false}
                                        />
                                    </div>

                                    <div className="col-md-6">
                                        <label className="form-label fw-bold">
                                            <i className="bi bi-dash-circle me-1"></i>
                                            Exclude Companies
                                        </label>
                                        <AsyncSelectField
                                            endpoint="masters/companies/"
                                            labelField="name"
                                            valueField="id"
                                            value={excludeCompanies}
                                            onChange={handleExcludeCompanyChange}
                                            isMulti={true}
                                            placeholder="Select companies to exclude..."
                                            loadOnMount={false}
                                        />
                                    </div>
                                </div>
                                {hasActiveFilters && (
                                    <div className="mt-3">
                                        <button className="btn btn-outline-secondary" onClick={handleClearFilters}>
                                            <i className="bi bi-x-circle me-2"></i>
                                            Clear All Filters
                                        </button>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Norm Tabs */}
            <div className="row mb-4">
                <div className="col-12">
                    <div className="card shadow-sm border-0">
                        <div className="card-body p-0">
                            <ul className="nav nav-tabs nav-fill" role="tablist" style={{ borderBottom: 'none' }}>
                                {availableNorms.map((norm) => {
                                    return (
                                        <li className="nav-item" key={norm} role="presentation">
                                            <button
                                                className={`nav-link ${activeNormTab === norm ? 'active' : ''}`}
                                                onClick={() => setActiveNormTab(norm)}
                                                type="button"
                                                role="tab"
                                                style={{
                                                    fontWeight: activeNormTab === norm ? 'bold' : 'normal',
                                                    borderBottom: activeNormTab === norm ? '3px solid #667eea' : 'none',
                                                    background: activeNormTab === norm ? 'linear-gradient(135deg, #f093fb11 0%, #f5576c11 100%)' : 'transparent'
                                                }}
                                            >
                                                <i className="bi bi-tag-fill me-2"></i>
                                                {norm}
                                                {loading && activeNormTab === norm && (
                                                    <span className="spinner-border spinner-border-sm ms-2" role="status"></span>
                                                )}
                                            </button>
                                        </li>
                                    );
                                })}
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            {/* Report Tables - Only show active norm */}
            <div className="row">
                <div className="col-12">
                    {activeNormTab && reportData.licenses_by_norm_notification[activeNormTab] && (
                        <div>
                            {/* Notifications within active norm */}
                            {Object.entries(reportData.licenses_by_norm_notification[activeNormTab]).sort().map(([notification, licenses]) => (
                                <div key={`${activeNormTab}-${notification}`} className="mb-4">
                                    <div className="card shadow-sm border-0">
                                        <div className="card-header bg-gradient text-white d-flex justify-content-between align-items-center" style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' }}>
                                            <div>
                                                <h5 className="mb-0">
                                                    <i className="bi bi-bell-fill me-2"></i>
                                                    Notification: {notification}
                                                </h5>
                                                <small className="opacity-75">
                                                    {licenses.length} License{licenses.length !== 1 ? 's' : ''}
                                                </small>
                                            </div>
                                            <span className="badge bg-white text-dark">{licenses.length}</span>
                                        </div>
                                <div className="card-body p-0">
                                    <div className="table-responsive">
                                        <table className="table table-hover table-sm mb-0">
                                            <thead style={{ position: 'sticky', top: 0, zIndex: 10 }}>
                                                <tr className="table-light">
                                                    <th className="text-center" style={{ minWidth: '60px' }}>Sr No</th>
                                                    <th style={{ minWidth: '120px' }}>DFIA No</th>
                                                    <th style={{ minWidth: '100px' }}>DFIA Dt</th>
                                                    <th style={{ minWidth: '100px' }}>Expiry Dt</th>
                                                    <th style={{ minWidth: '150px' }}>Exporter</th>
                                                    <th className="text-end" style={{ minWidth: '100px' }}>Total CIF</th>
                                                    <th className="text-end" style={{ minWidth: '110px' }}>Balance CIF</th>
                                                    {reportData.items.filter(item => item.name).map(item => {
                                                        const colSpan = item.has_restriction ? 7 : 5;
                                                        return (
                                                            <th key={`${item.id}-qty`} colSpan={colSpan} className="text-center bg-info bg-opacity-10" style={{ minWidth: '200px' }}>
                                                                <i className="bi bi-box-seam me-1"></i>
                                                                {item.name}
                                                            </th>
                                                        );
                                                    })}
                                                </tr>
                                                <tr className="table-secondary">
                                                    <th colSpan="7"></th>
                                                    {reportData.items.filter(item => item.name).map(item => (
                                                        <React.Fragment key={`${item.id}-headers`}>
                                                            <th style={{ minWidth: '90px', fontSize: '0.85rem' }}>HSN Code</th>
                                                            <th style={{ minWidth: '150px', fontSize: '0.85rem' }}>Description</th>
                                                            <th className="text-end" style={{ minWidth: '90px', fontSize: '0.85rem' }}>Total QTY</th>
                                                            <th className="text-end" style={{ minWidth: '100px', fontSize: '0.85rem' }}>Debited QTY</th>
                                                            <th className="text-end" style={{ minWidth: '110px', fontSize: '0.85rem' }}>Available QTY</th>
                                                            {item.has_restriction && (
                                                                <>
                                                                    <th className="text-center" style={{ minWidth: '90px', fontSize: '0.85rem' }}>Restriction %</th>
                                                                    <th className="text-end" style={{ minWidth: '120px', fontSize: '0.85rem' }}>Restriction Val</th>
                                                                </>
                                                            )}
                                                        </React.Fragment>
                                                    ))}
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {licenses.map((license, idx) => (
                                                    <tr key={license.license_number} className="align-middle">
                                                        <td className="text-center fw-bold">{idx + 1}</td>
                                                        <td className="text-nowrap">{license.license_number}</td>
                                                        <td className="text-nowrap">{license.license_date}</td>
                                                        <td className="text-nowrap">{license.license_expiry_date}</td>
                                                        <td className="text-truncate" style={{ maxWidth: '200px' }} title={license.exporter}>
                                                            {license.exporter}
                                                        </td>
                                                        <td className="text-end fw-semibold">{license.total_cif.toFixed(2)}</td>
                                                        <td className="text-end fw-semibold text-success">{license.balance_cif.toFixed(2)}</td>
                                                        {reportData.items.filter(item => item.name).map(item => {
                                                            const itemData = license.items[item.name] || {};
                                                            const hasData = itemData.quantity > 0;
                                                            return (
                                                                <React.Fragment key={`${license.license_number}-${item.id}`}>
                                                                    <td className={hasData ? 'bg-light' : ''}>
                                                                        {itemData.hs_code || '-'}
                                                                    </td>
                                                                    <td className={`text-truncate ${hasData ? 'bg-light' : ''}`} style={{ maxWidth: '180px' }} title={itemData.description || ''}>
                                                                        {itemData.description || '-'}
                                                                    </td>
                                                                    <td className={`text-end ${hasData ? 'bg-light fw-semibold' : ''}`}>
                                                                        {itemData.quantity ? itemData.quantity.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className={`text-end ${hasData ? 'bg-light text-warning' : ''}`}>
                                                                        {itemData.debited_quantity ? itemData.debited_quantity.toFixed(3) : '-'}
                                                                    </td>
                                                                    <td className={`text-end ${hasData ? 'bg-light text-success fw-semibold' : ''}`}>
                                                                        {itemData.available_quantity ? itemData.available_quantity.toFixed(3) : '-'}
                                                                    </td>
                                                                    {item.has_restriction && (
                                                                        <>
                                                                            <td className={`text-center ${hasData ? 'bg-light' : ''}`}>
                                                                                {itemData.restriction !== null && itemData.restriction !== undefined ? (
                                                                                    <span className="badge bg-info">{itemData.restriction}%</span>
                                                                                ) : '-'}
                                                                            </td>
                                                                            <td className={`text-end ${hasData ? 'bg-light fw-semibold' : ''}`}>
                                                                                {itemData.restriction_value ? itemData.restriction_value.toFixed(2) : '-'}
                                                                            </td>
                                                                        </>
                                                                    )}
                                                                </React.Fragment>
                                                            );
                                                        })}
                                                    </tr>
                                                ))}
                                                <tr className="table-warning fw-bold" style={{ position: 'sticky', bottom: 0, backgroundColor: '#fff3cd' }}>
                                                    <td colSpan="5" className="text-uppercase">
                                                        <i className="bi bi-calculator me-2"></i>
                                                        TOTAL
                                                    </td>
                                                    <td className="text-end text-primary">
                                                        {licenses.reduce((sum, lic) => sum + lic.total_cif, 0).toFixed(2)}
                                                    </td>
                                                    <td className="text-end text-success">
                                                        {licenses.reduce((sum, lic) => sum + lic.balance_cif, 0).toFixed(2)}
                                                    </td>
                                                    {reportData.items.filter(item => item.name).map(item => {
                                                        const totalQty = licenses.reduce((sum, lic) => {
                                                            return sum + (lic.items[item.name]?.quantity || 0);
                                                        }, 0);
                                                        const totalDebited = licenses.reduce((sum, lic) => {
                                                            return sum + (lic.items[item.name]?.debited_quantity || 0);
                                                        }, 0);
                                                        const totalAvail = licenses.reduce((sum, lic) => {
                                                            return sum + (lic.items[item.name]?.available_quantity || 0);
                                                        }, 0);
                                                        return (
                                                            <React.Fragment key={`total-${item.id}`}>
                                                                <td className="text-muted">-</td>
                                                                <td className="text-muted">-</td>
                                                                <td className="text-end text-primary">
                                                                    {totalQty > 0 ? totalQty.toFixed(3) : '-'}
                                                                </td>
                                                                <td className="text-end text-warning">
                                                                    {totalDebited > 0 ? totalDebited.toFixed(3) : '-'}
                                                                </td>
                                                                <td className="text-end text-success">
                                                                    {totalAvail > 0 ? totalAvail.toFixed(3) : '-'}
                                                                </td>
                                                                {item.has_restriction && (
                                                                    <>
                                                                        <td className="text-muted">-</td>
                                                                        <td className="text-muted">-</td>
                                                                    </>
                                                                )}
                                                            </React.Fragment>
                                                        );
                                                    })}
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            </div>
                                </div>
                            ))}
                        </div>
                    )}

                    {/* No data message */}
                    {reportData && Object.keys(reportData.licenses_by_norm_notification || {}).length === 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-inbox" style={{ fontSize: '3rem', color: '#ccc' }}></i>
                                <h5 className="mt-3 text-muted">No licenses found</h5>
                                <p className="text-muted">Try adjusting your filters to see more results.</p>
                            </div>
                        </div>
                    )}

                    {/* No norm selected message */}
                    {!activeNormTab && availableNorms.length > 0 && (
                        <div className="card shadow-sm border-0">
                            <div className="card-body text-center py-5">
                                <i className="bi bi-tag" style={{ fontSize: '3rem', color: '#ccc' }}></i>
                                <h5 className="mt-3 text-muted">Please select a norm tab above</h5>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
