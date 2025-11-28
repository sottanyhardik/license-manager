import React, {useState, useEffect} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";
import api from "../../api/axios";

export default function ItemPivotReport() {
    const [reportData, setReportData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [downloading, setDownloading] = useState(false);
    
    // Filter states
    const [sionNorm, setSionNorm] = useState('');
    const [selectedCompanies, setSelectedCompanies] = useState([]);
    const [excludeCompanies, setExcludeCompanies] = useState([]);
    const [sionNorms, setSionNorms] = useState([]);

    useEffect(() => {
        loadFilterOptions();
    }, []);

    // Auto-apply filters when they change
    useEffect(() => {
        loadReport();
    }, [sionNorm, selectedCompanies, excludeCompanies]);

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

    const loadReport = async () => {
        setLoading(true);
        try {
            let url = 'license/reports/item-pivot/?format=json&days=30';
            
            if (sionNorm) {
                url += `&sion_norm=${sionNorm}`;
            }
            if (selectedCompanies.length > 0) {
                url += `&company_ids=${selectedCompanies.join(',')}`;
            }
            if (excludeCompanies.length > 0) {
                url += `&exclude_company_ids=${excludeCompanies.join(',')}`;
            }
            
            const response = await api.get(url);
            setReportData(response.data);
        } catch (error) {
            console.error('Error loading report:', error);
            alert('Failed to load report. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    const handleExport = async () => {
        setDownloading(true);
        try {
            let url = 'license/reports/item-pivot/?format=excel&days=30';
            
            if (sionNorm) {
                url += `&sion_norm=${sionNorm}`;
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
        setSionNorm('');
        setSelectedCompanies([]);
        setExcludeCompanies([]);
    };

    if (loading) {
        return (
            <div className="container-fluid text-center mt-5">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-3">Loading report...</p>
            </div>
        );
    }

    if (!reportData) {
        return (
            <div className="container-fluid">
                <div className="alert alert-warning">No report data available.</div>
            </div>
        );
    }

    return (
        <div className="container-fluid">
            <div className="row mb-3">
                <div className="col-12 d-flex justify-content-between align-items-center">
                    <div>
                        <h2>Item Pivot Report</h2>
                        <p className="text-muted mb-0">
                            Licenses with items as column headers showing quantities and values
                        </p>
                    </div>
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
                                Download Excel
                            </>
                        )}
                    </button>
                </div>
            </div>

            {/* Filters - Vertical Layout */}
            <div className="row mb-3">
                <div className="col-md-3">
                    <div className="card">
                        <div className="card-body">
                            <h5 className="card-title mb-3">Filters</h5>
                            
                            <div className="mb-3">
                                <label className="form-label fw-bold">SION Norm</label>
                                <select 
                                    className="form-select" 
                                    value={sionNorm}
                                    onChange={(e) => setSionNorm(e.target.value)}
                                >
                                    <option value="">All Norms</option>
                                    {Array.isArray(sionNorms) && sionNorms.map(norm => (
                                        <option key={norm.id} value={norm.norm_class}>
                                            {norm.norm_class}
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="mb-3">
                                <label className="form-label fw-bold">Include Companies</label>
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

                            <div className="mb-3">
                                <label className="form-label fw-bold">Exclude Companies</label>
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

                            <div className="d-grid">
                                <button className="btn btn-secondary" onClick={handleClearFilters}>
                                    <i className="bi bi-x-circle me-2"></i>
                                    Clear Filters
                                </button>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="col-md-9">

                    {/* Tables split by notification */}
                    {Object.entries(reportData.licenses_by_notification || {}).sort().map(([notification, licenses]) => (
                        <div key={notification} className="mb-4">
                            <h4 className="bg-primary text-white p-2">Notification: {notification}</h4>
                        <div className="table-responsive">
                            <table className="table table-bordered table-sm">
                                <thead className="table-primary">
                                    <tr>
                                        <th>Sr No</th>
                                        <th>DFIA No</th>
                                        <th>DFIA Dt</th>
                                        <th>Expiry Dt</th>
                                        <th>Exporter</th>
                                        <th>Total CIF</th>
                                        <th>Balance CIF</th>
                                        {reportData.items.filter(item => item.name).map(item => {
                                            const colSpan = item.has_restriction ? 7 : 5;
                                            return (
                                                <th key={`${item.id}-qty`} colSpan={colSpan} className="text-center">
                                                    {item.name}
                                                </th>
                                            );
                                        })}
                                    </tr>
                                    <tr>
                                        <th colSpan="7"></th>
                                        {reportData.items.filter(item => item.name).map(item => (
                                            <React.Fragment key={`${item.id}-headers`}>
                                                <th>HSN Code</th>
                                                <th>Product Description</th>
                                                <th>Total QTY</th>
                                                <th>Debited QTY</th>
                                                <th>Available QTY</th>
                                                {item.has_restriction && (
                                                    <>
                                                        <th>Restriction %</th>
                                                        <th>Restriction Value</th>
                                                    </>
                                                )}
                                            </React.Fragment>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {licenses.map((license, idx) => (
                                        <tr key={license.license_number}>
                                            <td>{idx + 1}</td>
                                            <td>{license.license_number}</td>
                                            <td>{license.license_date}</td>
                                            <td>{license.license_expiry_date}</td>
                                            <td>{license.exporter}</td>
                                            <td className="text-end">{license.total_cif.toFixed(2)}</td>
                                            <td className="text-end">{license.balance_cif.toFixed(2)}</td>
                                            {reportData.items.filter(item => item.name).map(item => {
                                                const itemData = license.items[item.name] || {};
                                                return (
                                                    <React.Fragment key={`${license.license_number}-${item.id}`}>
                                                        <td>
                                                            {itemData.hs_code || '-'}
                                                        </td>
                                                        <td>
                                                            {itemData.description || '-'}
                                                        </td>
                                                        <td className="text-end">
                                                            {itemData.quantity ? itemData.quantity.toFixed(3) : '-'}
                                                        </td>
                                                        <td className="text-end">
                                                            {itemData.debited_quantity ? itemData.debited_quantity.toFixed(3) : '-'}
                                                        </td>
                                                        <td className="text-end">
                                                            {itemData.available_quantity ? itemData.available_quantity.toFixed(3) : '-'}
                                                        </td>
                                                        {item.has_restriction && (
                                                            <>
                                                                <td className="text-center">
                                                                    {itemData.restriction !== null && itemData.restriction !== undefined ? itemData.restriction : '-'}
                                                                </td>
                                                                <td className="text-end">
                                                                    {itemData.restriction_value ? itemData.restriction_value.toFixed(2) : '-'}
                                                                </td>
                                                            </>
                                                        )}
                                                    </React.Fragment>
                                                );
                                            })}
                                        </tr>
                                    ))}
                                    <tr className="table-secondary fw-bold">
                                        <td colSpan="5">TOTAL</td>
                                        <td className="text-end">
                                            {licenses.reduce((sum, lic) => sum + lic.total_cif, 0).toFixed(2)}
                                        </td>
                                        <td className="text-end">
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
                                                    <td>-</td>
                                                    <td>-</td>
                                                    <td className="text-end">
                                                        {totalQty > 0 ? totalQty.toFixed(3) : '-'}
                                                    </td>
                                                    <td className="text-end">
                                                        {totalDebited > 0 ? totalDebited.toFixed(3) : '-'}
                                                    </td>
                                                    <td className="text-end">
                                                        {totalAvail > 0 ? totalAvail.toFixed(3) : '-'}
                                                    </td>
                                                    {item.has_restriction && (
                                                        <>
                                                            <td>-</td>
                                                            <td>-</td>
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
                    ))}
                </div>
            </div>
        </div>
    );
}
