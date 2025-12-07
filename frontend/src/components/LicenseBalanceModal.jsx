import { useState, useEffect } from 'react';
import api from '../api/axios';
import AsyncSelect from 'react-select/async';
import { toast } from 'react-toastify';

export default function LicenseBalanceModal({ show, onHide, licenseId }) {
    const [loading, setLoading] = useState(false);
    const [licenseData, setLicenseData] = useState(null);
    const [expandedItem, setExpandedItem] = useState(null);
    const [usageData, setUsageData] = useState(null);

    // Inline editing state
    const [editingItemId, setEditingItemId] = useState(null);
    const [editingItems, setEditingItems] = useState([]);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (show && licenseId) {
            fetchLicenseData();
        }
    }, [show, licenseId]);

    const fetchLicenseData = async () => {
        setLoading(true);
        try {
            const { data } = await api.get(`/licenses/${licenseId}/`);
            setLicenseData(data);
        } catch (error) {
            console.error('Error fetching license data:', error);
            toast.error('Failed to load license data');
        } finally {
            setLoading(false);
        }
    };

    const fetchItemUsage = async (item, type) => {
        try {
            const response = await api.get(`/licenses/${licenseId}/item-usage/`, {
                params: {
                    item_id: item.id,
                    type: type
                }
            });
            setUsageData(response.data);
        } catch (error) {
            console.error('Error fetching item usage:', error);
            setUsageData({
                boes: [],
                allotments: []
            });
        }
    };

    const handleRowClick = (item, type) => {
        // Don't expand if we're editing
        if (editingItemId) return;

        if (expandedItem?.id === item.id) {
            setExpandedItem(null);
            setUsageData(null);
        } else {
            setExpandedItem({ ...item, type });
            fetchItemUsage(item, type);
        }
    };

    const loadItemOptions = async (inputValue) => {
        try {
            const { data } = await api.get('/masters/item-names/', {
                params: {
                    search: inputValue,
                    page_size: 50
                }
            });
            return data.results.map(item => ({
                value: item.id,
                label: item.name
            }));
        } catch (error) {
            console.error('Error loading items:', error);
            return [];
        }
    };

    const handleEditClick = (e, item) => {
        e.stopPropagation();
        setEditingItemId(item.id);
        // Convert items_detail to react-select format
        const selectedItems = (item.items_detail || []).map(i => ({
            value: i.id,
            label: i.name
        }));
        setEditingItems(selectedItems);
    };

    const handleSaveItems = async (e, item) => {
        e.stopPropagation();
        setSaving(true);
        try {
            // Extract just the IDs
            const itemIds = editingItems.map(i => i.value);

            await api.patch(`/licenses/${licenseId}/`, {
                import_license: licenseData.import_license.map(importItem => {
                    if (importItem.id === item.id) {
                        return {
                            ...importItem,
                            items: itemIds
                        };
                    }
                    return importItem;
                })
            });

            // Update local state without reloading
            setLicenseData(prevData => ({
                ...prevData,
                import_license: prevData.import_license.map(importItem => {
                    if (importItem.id === item.id) {
                        return {
                            ...importItem,
                            items: itemIds,
                            items_detail: editingItems.map(i => ({
                                id: i.value,
                                name: i.label
                            }))
                        };
                    }
                    return importItem;
                })
            }));

            toast.success('Items updated successfully');
            setEditingItemId(null);
        } catch (error) {
            console.error('Error updating items:', error);
            toast.error('Failed to update items');
        } finally {
            setSaving(false);
        }
    };

    const handleCancelEdit = (e) => {
        e.stopPropagation();
        setEditingItemId(null);
        setEditingItems([]);
    };

    if (!show) return null;

    return (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
            <div className="modal-dialog modal-xl" style={{ maxWidth: '95%' }}>
                <div className="modal-content">
                    <div className="modal-header">
                        <h5 className="modal-title">
                            License Balance Details{licenseData ? ` - ${licenseData.license_number}` : ''}
                        </h5>
                        <button type="button" className="btn-close" onClick={onHide}></button>
                    </div>
                    <div className="modal-body">
                        {loading || !licenseData ? (
                            <div className="text-center py-5">
                                <div className="spinner-border text-primary"></div>
                                <p className="mt-2">Loading...</p>
                            </div>
                        ) : (
                            <>
                                {/* Export Items */}
                                {licenseData.export_license && licenseData.export_license.length > 0 && (
                                    <div className="mb-5">
                                        <h5 className="mb-3">Export Items</h5>
                                        <table className="table table-bordered table-hover">
                                            <thead className="table-light">
                                                <tr>
                                                    <th>Item</th>
                                                    <th>Total CIF</th>
                                                    <th>Balance CIF</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {licenseData.export_license.map((item) => (
                                                    <>
                                                        <tr
                                                            key={item.id}
                                                            onClick={() => handleRowClick(item, 'export')}
                                                            style={{ cursor: 'pointer' }}
                                                            className={expandedItem?.id === item.id ? 'table-active' : ''}
                                                        >
                                                            <td>{item.description || item.norm_class_label || 'None'}</td>
                                                            <td>{parseFloat(item.cif_fc || item.fob_fc || 0).toFixed(2)}</td>
                                                            <td>{parseFloat(licenseData.balance_cif || 0).toFixed(2)}</td>
                                                        </tr>
                                                        {expandedItem?.id === item.id && usageData && (
                                                            <tr>
                                                                <td colSpan="3">
                                                                    <div className="p-3 bg-light">
                                                                        <h6>Usage Details:</h6>

                                                                        {/* BOE Table */}
                                                                        {usageData.boes && usageData.boes.length > 0 ? (
                                                                            <div className="mb-3">
                                                                                <strong>BOEs:</strong>
                                                                                <table className="table table-sm table-bordered mt-2">
                                                                                    <thead className="table-secondary">
                                                                                        <tr>
                                                                                            <th>BOE Number</th>
                                                                                            <th>Date</th>
                                                                                            <th>Port</th>
                                                                                            <th>Company</th>
                                                                                            <th>Qty</th>
                                                                                            <th>CIF $</th>
                                                                                            <th>CIF INR</th>
                                                                                        </tr>
                                                                                    </thead>
                                                                                    <tbody>
                                                                                        {usageData.boes.map((boe) => (
                                                                                            <tr key={boe.id}>
                                                                                                <td>{boe.bill_of_entry_number}</td>
                                                                                                <td>{boe.date ? new Date(boe.date).toLocaleDateString() : '-'}</td>
                                                                                                <td>{boe.port || '-'}</td>
                                                                                                <td>{boe.company || '-'}</td>
                                                                                                <td>{parseFloat(boe.quantity || 0).toFixed(2)}</td>
                                                                                                <td>{parseFloat(boe.cif_fc || 0).toFixed(2)}</td>
                                                                                                <td>{parseFloat(boe.cif_inr || 0).toFixed(2)}</td>
                                                                                            </tr>
                                                                                        ))}
                                                                                    </tbody>
                                                                                </table>
                                                                            </div>
                                                                        ) : (
                                                                            <p className="text-muted">No BOE usage found</p>
                                                                        )}

                                                                        {/* Allotment Table */}
                                                                        {usageData.allotments && usageData.allotments.length > 0 && (
                                                                            <div>
                                                                                <strong>Allotments:</strong>
                                                                                <table className="table table-sm table-bordered mt-2">
                                                                                    <thead className="table-secondary">
                                                                                        <tr>
                                                                                            <th>Company</th>
                                                                                            <th>Qty</th>
                                                                                            <th>CIF $</th>
                                                                                            <th>CIF INR</th>
                                                                                        </tr>
                                                                                    </thead>
                                                                                    <tbody>
                                                                                        {usageData.allotments.map((allotment) => (
                                                                                            <tr key={allotment.id}>
                                                                                                <td>{allotment.company || '-'}</td>
                                                                                                <td>{parseFloat(allotment.quantity || 0).toFixed(2)}</td>
                                                                                                <td>{parseFloat(allotment.cif_fc || 0).toFixed(2)}</td>
                                                                                                <td>{parseFloat(allotment.cif_inr || 0).toFixed(2)}</td>
                                                                                            </tr>
                                                                                        ))}
                                                                                    </tbody>
                                                                                </table>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                </td>
                                                            </tr>
                                                        )}
                                                    </>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}

                                {/* Import Items */}
                                {licenseData.import_license && licenseData.import_license.length > 0 && (
                                    <div>
                                        <h5 className="mb-3">Import Items</h5>
                                        <div className="table-responsive">
                                            <table className="table table-bordered table-hover table-sm">
                                                <thead className="table-light">
                                                    <tr>
                                                        <th style={{ minWidth: '50px' }}>Sr No</th>
                                                        <th style={{ minWidth: '100px' }}>HS Code</th>
                                                        <th style={{ minWidth: '200px' }}>Description</th>
                                                        <th style={{ minWidth: '250px' }}>Item</th>
                                                        <th style={{ minWidth: '100px' }}>Total Quantity</th>
                                                        <th style={{ minWidth: '100px' }}>Allotted Qty</th>
                                                        <th style={{ minWidth: '100px' }}>Debited Qty</th>
                                                        <th style={{ minWidth: '100px' }}>Available Qty</th>
                                                        <th style={{ minWidth: '100px' }}>CIF FC</th>
                                                        <th style={{ minWidth: '100px' }}>Balance CIF FC</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {licenseData.import_license.map((item, index) => (
                                                        <>
                                                            <tr
                                                                key={item.id}
                                                                onClick={() => handleRowClick(item, 'import')}
                                                                style={{ cursor: editingItemId ? 'default' : 'pointer' }}
                                                                className={expandedItem?.id === item.id ? 'table-active' : ''}
                                                            >
                                                                <td>{item.serial_number || index + 1}</td>
                                                                <td>{item.hs_code_label || item.hs_code || '-'}</td>
                                                                <td>{item.description || '-'}</td>
                                                                <td onClick={(e) => e.stopPropagation()}>
                                                                    {editingItemId === item.id ? (
                                                                        <div className="d-flex align-items-center gap-1">
                                                                            <AsyncSelect
                                                                                isMulti
                                                                                cacheOptions
                                                                                defaultOptions
                                                                                value={editingItems}
                                                                                loadOptions={loadItemOptions}
                                                                                onChange={setEditingItems}
                                                                                placeholder="Select items..."
                                                                                className="flex-grow-1"
                                                                                styles={{
                                                                                    control: (base) => ({
                                                                                        ...base,
                                                                                        minHeight: '32px',
                                                                                        fontSize: '0.875rem'
                                                                                    })
                                                                                }}
                                                                            />
                                                                            <button
                                                                                className="btn btn-sm btn-success"
                                                                                onClick={(e) => handleSaveItems(e, item)}
                                                                                disabled={saving}
                                                                            >
                                                                                <i className="bi bi-check"></i>
                                                                            </button>
                                                                            <button
                                                                                className="btn btn-sm btn-secondary"
                                                                                onClick={handleCancelEdit}
                                                                                disabled={saving}
                                                                            >
                                                                                <i className="bi bi-x"></i>
                                                                            </button>
                                                                        </div>
                                                                    ) : (
                                                                        <div
                                                                            className="d-flex justify-content-between align-items-center"
                                                                            style={{ cursor: 'pointer' }}
                                                                            title="Click to edit"
                                                                        >
                                                                            <span>
                                                                                {item.items_detail && item.items_detail.length > 0
                                                                                    ? item.items_detail.map(i => i.name).join(', ')
                                                                                    : '-'}
                                                                            </span>
                                                                            <i
                                                                                className="bi bi-pencil text-muted ms-2"
                                                                                onClick={(e) => handleEditClick(e, item)}
                                                                                style={{ fontSize: '0.8rem' }}
                                                                            ></i>
                                                                        </div>
                                                                    )}
                                                                </td>
                                                                <td>{parseFloat(item.quantity || 0).toFixed(2)}</td>
                                                                <td>{parseFloat(item.allotted_quantity || 0).toFixed(2)}</td>
                                                                <td>{parseFloat(item.debited_quantity || 0).toFixed(2)}</td>
                                                                <td>{parseFloat(item.available_quantity || 0).toFixed(2)}</td>
                                                                <td>{parseFloat(item.cif_fc || 0).toFixed(2)}</td>
                                                                <td>{parseFloat(item.balance_cif_fc || 0).toFixed(2)}</td>
                                                            </tr>
                                                            {expandedItem?.id === item.id && usageData && (
                                                                <tr>
                                                                    <td colSpan="10">
                                                                        <div className="p-3 bg-light">
                                                                            <h6>Usage Details:</h6>

                                                                            {/* BOE Table */}
                                                                            {usageData.boes && usageData.boes.length > 0 ? (
                                                                                <div className="mb-3">
                                                                                    <strong>BOEs:</strong>
                                                                                    <table className="table table-sm table-bordered mt-2">
                                                                                        <thead className="table-secondary">
                                                                                            <tr>
                                                                                                <th>BOE Number</th>
                                                                                                <th>Date</th>
                                                                                                <th>Port</th>
                                                                                                <th>Company</th>
                                                                                                <th>Qty</th>
                                                                                                <th>CIF $</th>
                                                                                                <th>CIF INR</th>
                                                                                            </tr>
                                                                                        </thead>
                                                                                        <tbody>
                                                                                            {usageData.boes.map((boe) => (
                                                                                                <tr key={boe.id}>
                                                                                                    <td>{boe.bill_of_entry_number}</td>
                                                                                                    <td>{boe.date ? new Date(boe.date).toLocaleDateString() : '-'}</td>
                                                                                                    <td>{boe.port || '-'}</td>
                                                                                                    <td>{boe.company || '-'}</td>
                                                                                                    <td>{parseFloat(boe.quantity || 0).toFixed(2)}</td>
                                                                                                    <td>{parseFloat(boe.cif_fc || 0).toFixed(2)}</td>
                                                                                                    <td>{parseFloat(boe.cif_inr || 0).toFixed(2)}</td>
                                                                                                </tr>
                                                                                            ))}
                                                                                        </tbody>
                                                                                    </table>
                                                                                </div>
                                                                            ) : (
                                                                                <p className="text-muted mb-2">No BOE usage found</p>
                                                                            )}

                                                                            {/* Allotment Table */}
                                                                            {usageData.allotments && usageData.allotments.length > 0 ? (
                                                                                <div>
                                                                                    <strong>Allotments:</strong>
                                                                                    <table className="table table-sm table-bordered mt-2">
                                                                                        <thead className="table-secondary">
                                                                                            <tr>
                                                                                                <th>Company</th>
                                                                                                <th>Qty</th>
                                                                                                <th>CIF $</th>
                                                                                                <th>CIF INR</th>
                                                                                            </tr>
                                                                                        </thead>
                                                                                        <tbody>
                                                                                            {usageData.allotments.map((allotment) => (
                                                                                                <tr key={allotment.id}>
                                                                                                    <td>{allotment.company || '-'}</td>
                                                                                                    <td>{parseFloat(allotment.quantity || 0).toFixed(2)}</td>
                                                                                                    <td>{parseFloat(allotment.cif_fc || 0).toFixed(2)}</td>
                                                                                                    <td>{parseFloat(allotment.cif_inr || 0).toFixed(2)}</td>
                                                                                                </tr>
                                                                                            ))}
                                                                                        </tbody>
                                                                                    </table>
                                                                                </div>
                                                                            ) : (
                                                                                <p className="text-muted mb-2">No Allotment usage found</p>
                                                                            )}

                                                                            {/* Balance Calculation */}
                                                                            <div className="mt-3 pt-2 border-top">
                                                                                <strong>Balance Calculation:</strong>
                                                                                <div className="ms-3 mt-2">
                                                                                    <div className="row">
                                                                                        <div className="col-md-6">
                                                                                            <small className="text-muted">
                                                                                                Balance Quantity = Total Quantity - Debited Qty - Allotted Qty
                                                                                            </small>
                                                                                        </div>
                                                                                        <div className="col-md-6 text-end">
                                                                                            <strong>
                                                                                                Balance: {parseFloat(
                                                                                                    (item.quantity || 0) -
                                                                                                    (item.debited_quantity || 0) -
                                                                                                    (item.allotted_quantity || 0)
                                                                                                ).toFixed(2)}
                                                                                            </strong>
                                                                                        </div>
                                                                                    </div>
                                                                                </div>
                                                                            </div>
                                                                        </div>
                                                                    </td>
                                                                </tr>
                                                            )}
                                                        </>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                )}
                            </>
                        )}
                    </div>
                    <div className="modal-footer">
                        <button type="button" className="btn btn-secondary" onClick={onHide}>
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
