import React, { useState, useEffect } from "react";
import api from "../../api/axios";

/**
 * Reusable SION Norm Report Component
 * Displays licenses for a specific SION norm, grouped by notification
 */
export default function SionNormReport({ sionNorm, title }) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
        is_expired: "False",
        is_null: "False",
        sion_norm: sionNorm,
    });

    const fetchReport = async () => {
        try {
            setLoading(true);
            const params = new URLSearchParams(filters).toString();
            const response = await api.get(`/licenses/active-dfia-report/?${params}`);
            setData(response.data);
        } catch (error) {
            console.error("Error fetching SION norm report:", error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchReport();
    }, [filters]);

    const handleFilterChange = (filterName, value) => {
        setFilters(prev => ({
            ...prev,
            [filterName]: value
        }));
    };

    const formatNumber = (num, decimals = 2) => {
        if (num === null || num === undefined) return "—";
        return Number(num).toLocaleString('en-IN', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return "—";
        const date = new Date(dateStr);
        const day = String(date.getDate()).padStart(2, '0');
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const year = date.getFullYear();
        return `${day}-${month}-${year}`;
    };

    const renderTableHeaders = () => (
        <thead className="table-primary" style={{fontSize: '10px', position: 'sticky', top: 0, zIndex: 10}}>
            <tr>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '40px'}}>Sr</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '120px'}}>DFIA No</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '90px'}}>DFIA Dt</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '90px'}}>Expiry Dt</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '200px'}}>Exporter</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '100px'}}>Total CIF</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '100px'}}>Balance CIF</th>
                <th colSpan="9" className="text-center">Vegetable Oil</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '80px'}}>10% Bal</th>
                <th colSpan="4" className="text-center">Juice</th>
                <th colSpan="4" className="text-center">Food Flavour</th>
                <th colSpan="2" className="text-center">Fruit</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '60px'}}>Lvng Agt</th>
                <th colSpan="2" className="text-center">Starch 1108</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '60px'}}>Strch 3505</th>
                <th colSpan="8" className="text-center">Milk & Milk</th>
                <th colSpan="3" className="text-center">PP</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '60px'}}>Al Foil</th>
                <th rowSpan="2" style={{verticalAlign: 'middle', minWidth: '80px'}}>Wastage</th>
            </tr>
            <tr>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '120px'}}>PD</th>
                <th style={{minWidth: '70px'}}>Tot Qty</th>
                <th style={{minWidth: '70px'}}>RBD Qty</th>
                <th style={{minWidth: '80px'}}>RBD CIF</th>
                <th style={{minWidth: '70px'}}>PKO Qty</th>
                <th style={{minWidth: '80px'}}>PKO CIF</th>
                <th style={{minWidth: '70px'}}>Olv Qty</th>
                <th style={{minWidth: '80px'}}>Olv CIF</th>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '100px'}}>PD</th>
                <th style={{minWidth: '70px'}}>Qty</th>
                <th style={{minWidth: '80px'}}>CIF</th>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '100px'}}>PD</th>
                <th style={{minWidth: '60px'}}>FF Qty</th>
                <th style={{minWidth: '60px'}}>DF Qty</th>
                <th style={{minWidth: '60px'}}>Qty</th>
                <th style={{minWidth: '80px'}}>CIF</th>
                <th style={{minWidth: '60px'}}>Qty</th>
                <th style={{minWidth: '80px'}}>CIF</th>
                <th style={{minWidth: '120px'}}>PD</th>
                <th style={{minWidth: '70px'}}>Tot Qty</th>
                <th style={{minWidth: '60px'}}>Chz Qty</th>
                <th style={{minWidth: '80px'}}>Chz CIF</th>
                <th style={{minWidth: '60px'}}>SWP Qty</th>
                <th style={{minWidth: '80px'}}>SWP CIF</th>
                <th style={{minWidth: '60px'}}>WPC Qty</th>
                <th style={{minWidth: '80px'}}>WPC CIF</th>
                <th style={{minWidth: '80px'}}>HSN</th>
                <th style={{minWidth: '100px'}}>PD</th>
                <th style={{minWidth: '60px'}}>Qty</th>
            </tr>
        </thead>
    );

    const renderLicenseRow = (license, index) => (
        <tr key={license.id} style={{fontSize: '9px'}}>
            <td>{index + 1}</td>
            <td>
                <a href={`/licenses/${license.id}`} target="_blank" rel="noopener noreferrer"
                   style={{fontSize: '9px', textDecoration: 'none'}}>
                    {license.license_number}
                </a>
            </td>
            <td>{formatDate(license.license_date)}</td>
            <td>{formatDate(license.license_expiry_date)}</td>
            <td style={{fontSize: '8px'}}>{license.exporter_name}</td>
            <td className="text-end">{formatNumber(license.total_cif)}</td>
            <td className="text-end">{formatNumber(license.balance_cif)}</td>
            <td>{license.vegetable_oil.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.vegetable_oil.description}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil.total_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil.rbd_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil.rbd_cif)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil.pko_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil.pko_cif)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil.olive_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.vegetable_oil.olive_cif)}</td>
            <td className="text-end">{formatNumber(license.ten_percent_balance)}</td>
            <td>{license.juice.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.juice.description}</td>
            <td className="text-end">{formatNumber(license.juice.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.juice.cif)}</td>
            <td>{license.food_flavour.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.food_flavour.description}</td>
            <td className="text-end">{formatNumber(license.food_flavour.ff_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.food_flavour.df_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.fruit_cocoa.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.fruit_cocoa.cif)}</td>
            <td className="text-end">{formatNumber(license.leavening_agent.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.starch_1108.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.starch_1108.cif)}</td>
            <td className="text-end">{formatNumber(license.starch_3505.qty, 2)}</td>
            <td style={{fontSize: '7px'}}>{license.milk_and_milk.description}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk.total_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk.cheese_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk.cheese_cif)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk.swp_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk.swp_cif)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk.wpc_qty, 2)}</td>
            <td className="text-end">{formatNumber(license.milk_and_milk.wpc_cif)}</td>
            <td>{license.pp.hsn_code}</td>
            <td style={{fontSize: '7px'}}>{license.pp.description}</td>
            <td className="text-end">{formatNumber(license.pp.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.aluminium_foil.qty, 2)}</td>
            <td className="text-end">{formatNumber(license.wastage_cif)}</td>
        </tr>
    );

    const renderTotalsRow = (totals, label) => (
        <tr className="table-warning fw-bold" style={{fontSize: '9px'}}>
            <td colSpan="5" className="text-end">{label}:</td>
            <td className="text-end">{formatNumber(totals.total_cif)}</td>
            <td className="text-end">{formatNumber(totals.balance_cif)}</td>
            <td colSpan="2"></td>
            <td className="text-end">{formatNumber(totals.veg_oil_total_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.rbd_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.rbd_cif)}</td>
            <td className="text-end">{formatNumber(totals.pko_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.pko_cif)}</td>
            <td className="text-end">{formatNumber(totals.olive_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.olive_cif)}</td>
            <td className="text-end">{formatNumber(totals.ten_percent_balance)}</td>
            <td colSpan="2"></td>
            <td className="text-end">{formatNumber(totals.juice_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.juice_cif)}</td>
            <td colSpan="2"></td>
            <td className="text-end">{formatNumber(totals.ff_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.df_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.fruit_cocoa_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.fruit_cocoa_cif)}</td>
            <td className="text-end">{formatNumber(totals.leavening_agent_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.starch_1108_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.starch_1108_cif)}</td>
            <td className="text-end">{formatNumber(totals.starch_3505_qty, 2)}</td>
            <td></td>
            <td className="text-end">{formatNumber(totals.milk_total_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.cheese_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.cheese_cif)}</td>
            <td className="text-end">{formatNumber(totals.swp_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.swp_cif)}</td>
            <td className="text-end">{formatNumber(totals.wpc_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.wpc_cif)}</td>
            <td colSpan="2"></td>
            <td className="text-end">{formatNumber(totals.pp_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.aluminium_foil_qty, 2)}</td>
            <td className="text-end">{formatNumber(totals.wastage_cif)}</td>
        </tr>
    );

    if (loading) {
        return (
            <div className="container-fluid p-4">
                <h2>{title}</h2>
                <div className="spinner-border mt-4" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
            </div>
        );
    }

    if (!data || !data.groups || data.groups.length === 0) {
        return (
            <div className="container-fluid p-4">
                <h2 className="mb-4">{title}</h2>
                <div className="card mb-4">
                    <div className="card-body">
                        <div className="row">
                            <div className="col-md-6">
                                <label className="form-label">Active/Expired</label>
                                <div>
                                    <div className="form-check form-check-inline">
                                        <input className="form-check-input" type="radio"
                                            checked={filters.is_expired === "False"}
                                            onChange={() => handleFilterChange("is_expired", "False")}
                                        />
                                        <label className="form-check-label">Active</label>
                                    </div>
                                    <div className="form-check form-check-inline">
                                        <input className="form-check-input" type="radio"
                                            checked={filters.is_expired === "True"}
                                            onChange={() => handleFilterChange("is_expired", "True")}
                                        />
                                        <label className="form-check-label">Expired</label>
                                    </div>
                                </div>
                            </div>
                            <div className="col-md-6">
                                <label className="form-label">Balance CIF</label>
                                <div>
                                    <div className="form-check form-check-inline">
                                        <input className="form-check-input" type="radio"
                                            checked={filters.is_null === "False"}
                                            onChange={() => handleFilterChange("is_null", "False")}
                                        />
                                        <label className="form-check-label">&gt; 200</label>
                                    </div>
                                    <div className="form-check form-check-inline">
                                        <input className="form-check-input" type="radio"
                                            checked={filters.is_null === "True"}
                                            onChange={() => handleFilterChange("is_null", "True")}
                                        />
                                        <label className="form-check-label">&lt; 200</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <p>No records found for SION Norm {sionNorm}</p>
            </div>
        );
    }

    // Get the first (and should be only) SION group since we're filtering by specific norm
    const sionGroup = data.groups[0];
    let globalSrNo = 0;

    return (
        <div className="container-fluid p-4">
            <h2 className="mb-4">{title}</h2>

            {/* Filters */}
            <div className="card mb-4">
                <div className="card-body">
                    <div className="row">
                        <div className="col-md-6">
                            <label className="form-label">Active/Expired</label>
                            <div>
                                <div className="form-check form-check-inline">
                                    <input className="form-check-input" type="radio"
                                        checked={filters.is_expired === "False"}
                                        onChange={() => handleFilterChange("is_expired", "False")}
                                    />
                                    <label className="form-check-label">Active</label>
                                </div>
                                <div className="form-check form-check-inline">
                                    <input className="form-check-input" type="radio"
                                        checked={filters.is_expired === "True"}
                                        onChange={() => handleFilterChange("is_expired", "True")}
                                    />
                                    <label className="form-check-label">Expired</label>
                                </div>
                            </div>
                        </div>
                        <div className="col-md-6">
                            <label className="form-label">Balance CIF</label>
                            <div>
                                <div className="form-check form-check-inline">
                                    <input className="form-check-input" type="radio"
                                        checked={filters.is_null === "False"}
                                        onChange={() => handleFilterChange("is_null", "False")}
                                    />
                                    <label className="form-check-label">&gt; 200</label>
                                </div>
                                <div className="form-check form-check-inline">
                                    <input className="form-check-input" type="radio"
                                        checked={filters.is_null === "True"}
                                        onChange={() => handleFilterChange("is_null", "True")}
                                    />
                                    <label className="form-check-label">&lt; 200</label>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Summary Cards */}
            <div className="row mb-4">
                <div className="col-md-4">
                    <div className="card">
                        <div className="card-body">
                            <h6 className="card-subtitle mb-2 text-muted">Total Licenses</h6>
                            <h3 className="card-title">{sionGroup.license_count}</h3>
                        </div>
                    </div>
                </div>
                <div className="col-md-4">
                    <div className="card">
                        <div className="card-body">
                            <h6 className="card-subtitle mb-2 text-muted">Total CIF</h6>
                            <h3 className="card-title">{formatNumber(sionGroup.totals.total_cif)}</h3>
                        </div>
                    </div>
                </div>
                <div className="col-md-4">
                    <div className="card">
                        <div className="card-body">
                            <h6 className="card-subtitle mb-2 text-muted">Balance CIF</h6>
                            <h3 className="card-title">{formatNumber(sionGroup.totals.balance_cif)}</h3>
                        </div>
                    </div>
                </div>
            </div>

            {/* Tables by Notification */}
            {sionGroup.notifications.map((notifGroup, notifIndex) => (
                <div key={notifIndex} className="mb-4">
                    <h5 className="mb-3 bg-secondary text-white p-2 rounded">
                        Notification: {notifGroup.notification_number}
                        <span className="ms-3 badge bg-light text-dark">
                            {notifGroup.license_count} licenses
                        </span>
                    </h5>

                    <div className="card">
                        <div className="card-body p-0">
                            <div className="table-responsive" style={{maxHeight: '600px', overflowY: 'auto'}}>
                                <table className="table table-bordered table-sm table-hover mb-0">
                                    {renderTableHeaders()}
                                    <tbody>
                                        {notifGroup.licenses.map((license) => {
                                            globalSrNo++;
                                            return renderLicenseRow(license, globalSrNo - 1);
                                        })}
                                        {renderTotalsRow(notifGroup.totals, `Total - ${notifGroup.notification_number}`)}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            ))}

            {/* SION Norm Grand Total */}
            <div className="card border-success mt-4">
                <div className="card-header bg-success text-white">
                    <h5 className="mb-0">Grand Total - SION Norm {sionNorm}</h5>
                </div>
                <div className="card-body p-0">
                    <div className="table-responsive">
                        <table className="table table-bordered table-sm mb-0">
                            {renderTableHeaders()}
                            <tbody>
                                {renderTotalsRow(sionGroup.totals, "Grand Total")}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
