import { useState, useEffect } from 'react';
import api from '../api/axios';
import AsyncSelect from 'react-select/async';
import { toast } from 'react-toastify';

// Inline Notes Component
function NotesSection({ licenseId, notes, onUpdate }) {
    const [isEditing, setIsEditing] = useState(false);
    const [noteText, setNoteText] = useState(notes);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        setNoteText(notes);
    }, [notes]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await api.patch(`/licenses/${licenseId}/`, {
                balance_report_notes: noteText
            });
            onUpdate(noteText);
            setIsEditing(false);
            toast.success('Notes saved successfully');
        } catch (error) {
            console.error('Error saving notes:', error);
            toast.error('Failed to save notes');
        } finally {
            setSaving(false);
        }
    };

    const handleCancel = () => {
        setNoteText(notes);
        setIsEditing(false);
    };

    return (
        <div>
            {isEditing ? (
                <div>
                    <textarea
                        className="form-control mb-2"
                        rows="4"
                        value={noteText}
                        onChange={(e) => setNoteText(e.target.value)}
                        placeholder="Enter notes here..."
                        style={{
                            fontSize: '0.875rem',
                            borderColor: '#667eea',
                            backgroundColor: '#fffacd'
                        }}
                    />
                    <div className="d-flex gap-2">
                        <button
                            className="btn btn-sm btn-primary"
                            onClick={handleSave}
                            disabled={saving}
                            style={{
                                backgroundColor: '#667eea',
                                borderColor: '#667eea'
                            }}
                        >
                            {saving ? 'Saving...' : 'Save'}
                        </button>
                        <button
                            className="btn btn-sm btn-secondary"
                            onClick={handleCancel}
                            disabled={saving}
                        >
                            Cancel
                        </button>
                    </div>
                </div>
            ) : (
                <div
                    onClick={() => setIsEditing(true)}
                    style={{
                        minHeight: '80px',
                        padding: '0.75rem',
                        backgroundColor: noteText ? '#fffacd' : '#f8f9fa',
                        border: '1px solid #dee2e6',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '0.875rem',
                        whiteSpace: 'pre-wrap',
                        transition: 'all 0.2s'
                    }}
                    onMouseOver={(e) => {
                        e.currentTarget.style.borderColor = '#667eea';
                        e.currentTarget.style.backgroundColor = noteText ? '#fffacd' : '#e9ecef';
                    }}
                    onMouseOut={(e) => {
                        e.currentTarget.style.borderColor = '#dee2e6';
                        e.currentTarget.style.backgroundColor = noteText ? '#fffacd' : '#f8f9fa';
                    }}
                >
                    {noteText || <span style={{ color: '#6c757d', fontStyle: 'italic' }}>Click to add notes...</span>}
                </div>
            )}
        </div>
    );
}

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
            // Filter items by license's norm class (get_norm_class)
            const params = {
                search: inputValue,
                page_size: 50
            };

            // Add norm class filter if available
            if (licenseData?.get_norm_class) {
                params.norm_class = licenseData.get_norm_class;
            }

            const { data } = await api.get('/masters/item-names/', {
                params
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

    const handleDownloadPDF = async () => {
        try {
            toast.info('Generating PDF file...');

            // Call backend to generate PDF - use license number instead of ID
            const token = localStorage.getItem('access');
            const licenseNumber = licenseData?.license_number || licenseId;
            const pdfUrl = `/api/licenses/${licenseNumber}/balance-pdf/?access_token=${token}`;

            // Open PDF in new tab to download
            window.open(pdfUrl, '_blank');

            toast.success('PDF file is being generated!');
        } catch (error) {
            console.error('Error generating PDF:', error);
            toast.error('Failed to generate PDF file');
        }
    };

    if (!show) return null;

    return (
        <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}>
            <div className="modal-dialog modal-xl" style={{ maxWidth: '95%' }}>
                <div className="modal-content" style={{
                    borderRadius: '12px',
                    boxShadow: '0 10px 40px rgba(0,0,0,0.2)',
                    border: 'none'
                }}>
                    <div className="modal-header" style={{
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        color: 'white',
                        borderTopLeftRadius: '12px',
                        borderTopRightRadius: '12px',
                        padding: '1.5rem',
                        borderBottom: 'none'
                    }}>
                        <h5 className="modal-title" style={{
                            fontWeight: '600',
                            fontSize: '1.25rem',
                            letterSpacing: '0.3px',
                            flex: 1
                        }}>
                            <i className="bi bi-file-text me-2"></i>
                            License Balance Report{licenseData ? ` - ${licenseData.license_number}` : ''}
                        </h5>
                        <div className="d-flex gap-3 align-items-center">
                            {licenseData && (
                                <button
                                    type="button"
                                    className="btn btn-sm"
                                    onClick={handleDownloadPDF}
                                    disabled={loading}
                                    style={{
                                        backgroundColor: 'white',
                                        color: '#667eea',
                                        border: 'none',
                                        fontWeight: '500',
                                        padding: '0.5rem 1rem',
                                        borderRadius: '6px',
                                        boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
                                        transition: 'all 0.3s'
                                    }}
                                    onMouseOver={(e) => {
                                        e.target.style.transform = 'translateY(-2px)';
                                        e.target.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                                    }}
                                    onMouseOut={(e) => {
                                        e.target.style.transform = 'translateY(0)';
                                        e.target.style.boxShadow = '0 2px 8px rgba(0,0,0,0.1)';
                                    }}
                                >
                                    <i className="bi bi-file-earmark-pdf me-2"></i>
                                    Download PDF
                                </button>
                            )}
                            <button
                                type="button"
                                className="btn-close btn-close-white"
                                onClick={onHide}
                                style={{ fontSize: '0.875rem' }}
                            ></button>
                        </div>
                    </div>
                    <div className="modal-body" style={{
                        padding: '2rem',
                        backgroundColor: '#f8f9fa'
                    }}>
                        {loading || !licenseData ? (
                            <div className="text-center py-5">
                                <div className="spinner-border" style={{ color: '#667eea' }}></div>
                                <p className="mt-2" style={{ color: '#6c757d' }}>Loading...</p>
                            </div>
                        ) : (
                            <>
                                {/* License Header Details */}
                                <div style={{
                                    backgroundColor: 'white',
                                    borderRadius: '8px',
                                    padding: '1.5rem',
                                    marginBottom: '1.5rem',
                                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                }}>
                                    <div className="table-responsive">
                                        <table className="table table-sm" style={{ marginBottom: '0', border: 'none' }}>
                                            <thead style={{ backgroundColor: '#667eea', color: 'white' }}>
                                                <tr>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>License Number</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>License Date</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>License Expiry Date</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Exporter Name</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Port Name</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr style={{ backgroundColor: '#f8f9fa' }}>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef', fontWeight: '500' }}>
                                                        {licenseData.license_number || '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {licenseData.license_date ? new Date(licenseData.license_date).toLocaleDateString('en-GB') : '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {licenseData.license_expiry_date ? new Date(licenseData.license_expiry_date).toLocaleDateString('en-GB') : '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {licenseData.exporter_name || '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {licenseData.port_name || '-'}
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                        <table className="table table-sm" style={{ marginBottom: '0', border: 'none', marginTop: '0.5rem' }}>
                                            <thead style={{ backgroundColor: '#667eea', color: 'white' }}>
                                                <tr>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Purchase Status</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Balance CIF</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Get Norm Class</th>
                                                    <th style={{ border: 'none', padding: '0.75rem', fontSize: '0.875rem', minWidth: '300px' }}>Latest Transfer</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <tr style={{ backgroundColor: '#f8f9fa' }}>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {licenseData.purchase_status || '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {parseFloat(licenseData.balance_cif || 0).toFixed(2)}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {licenseData.get_norm_class || '-'}
                                                    </td>
                                                    <td style={{ padding: '0.75rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                        {licenseData.latest_transfer || '-'}
                                                    </td>
                                                </tr>
                                            </tbody>
                                        </table>
                                    </div>
                                </div>

                                {/* Notes Section */}
                                <div className="mb-4" style={{
                                    backgroundColor: 'white',
                                    borderRadius: '8px',
                                    padding: '1.5rem',
                                    boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                }}>
                                    <div className="d-flex justify-content-between align-items-center mb-3">
                                        <h5 style={{
                                            color: '#2c3e50',
                                            fontWeight: '600',
                                            borderBottom: '2px solid #667eea',
                                            paddingBottom: '0.5rem',
                                            marginBottom: '0',
                                            flex: 1
                                        }}>
                                            <i className="bi bi-pencil-square me-2"></i>
                                            Notes
                                        </h5>
                                    </div>
                                    <NotesSection
                                        licenseId={licenseId}
                                        notes={licenseData.balance_report_notes || ''}
                                        onUpdate={(newNotes) => {
                                            setLicenseData(prev => ({ ...prev, balance_report_notes: newNotes }));
                                        }}
                                    />
                                </div>

                                {/* Export Items */}
                                {licenseData.export_license && licenseData.export_license.length > 0 && (
                                    <div className="mb-4" style={{
                                        backgroundColor: 'white',
                                        borderRadius: '8px',
                                        padding: '1.5rem',
                                        boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                    }}>
                                        <h5 className="mb-3" style={{
                                            color: '#2c3e50',
                                            fontWeight: '600',
                                            borderBottom: '2px solid #667eea',
                                            paddingBottom: '0.5rem'
                                        }}>
                                            <i className="bi bi-box-seam me-2"></i>
                                            Export Items
                                        </h5>
                                        <table className="table table-hover" style={{
                                            marginBottom: '0',
                                            border: 'none'
                                        }}>
                                            <thead style={{
                                                backgroundColor: '#667eea',
                                                color: 'white'
                                            }}>
                                                <tr>
                                                    <th style={{ border: 'none', padding: '0.75rem' }}>Item</th>
                                                    <th style={{ border: 'none', padding: '0.75rem' }}>Total CIF</th>
                                                    <th style={{ border: 'none', padding: '0.75rem' }}>Balance CIF</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {licenseData.export_license.map((item, index) => (
                                                    <>
                                                        <tr
                                                            key={item.id}
                                                            onClick={() => handleRowClick(item, 'export')}
                                                            style={{
                                                                cursor: 'pointer',
                                                                backgroundColor: expandedItem?.id === item.id ? '#f0f4ff' : index % 2 === 0 ? '#ffffff' : '#f8f9fa',
                                                                transition: 'all 0.2s'
                                                            }}
                                                            onMouseOver={(e) => {
                                                                if (expandedItem?.id !== item.id) {
                                                                    e.currentTarget.style.backgroundColor = '#e8eef9';
                                                                }
                                                            }}
                                                            onMouseOut={(e) => {
                                                                if (expandedItem?.id !== item.id) {
                                                                    e.currentTarget.style.backgroundColor = index % 2 === 0 ? '#ffffff' : '#f8f9fa';
                                                                }
                                                            }}
                                                        >
                                                            <td style={{ padding: '0.75rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                {item.description || item.norm_class_label || 'None'}
                                                            </td>
                                                            <td style={{ padding: '0.75rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                {parseFloat(item.cif_fc || item.fob_fc || 0).toFixed(2)}
                                                            </td>
                                                            <td style={{ padding: '0.75rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                {parseFloat(licenseData.balance_cif || 0).toFixed(2)}
                                                            </td>
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
                                    <div style={{
                                        backgroundColor: 'white',
                                        borderRadius: '8px',
                                        padding: '1.5rem',
                                        boxShadow: '0 2px 8px rgba(0,0,0,0.08)'
                                    }}>
                                        <h5 className="mb-3" style={{
                                            color: '#2c3e50',
                                            fontWeight: '600',
                                            borderBottom: '2px solid #764ba2',
                                            paddingBottom: '0.5rem'
                                        }}>
                                            <i className="bi bi-inbox me-2"></i>
                                            Import Items
                                        </h5>
                                        <div className="table-responsive">
                                            <table className="table table-hover table-sm" style={{
                                                marginBottom: '0',
                                                border: 'none'
                                            }}>
                                                <thead style={{
                                                    backgroundColor: '#764ba2',
                                                    color: 'white'
                                                }}>
                                                    <tr>
                                                        <th style={{ minWidth: '50px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Sr No</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>HS Code</th>
                                                        <th style={{ minWidth: '200px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Description</th>
                                                        <th style={{ minWidth: '250px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Item</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Total Quantity</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Allotted Qty</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Debited Qty</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Available Qty</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>CIF FC</th>
                                                        <th style={{ minWidth: '100px', border: 'none', padding: '0.75rem', fontSize: '0.875rem' }}>Balance CIF FC</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {licenseData.import_license.map((item, index) => (
                                                        <>
                                                            <tr
                                                                key={item.id}
                                                                onClick={() => handleRowClick(item, 'import')}
                                                                style={{
                                                                    cursor: editingItemId ? 'default' : 'pointer',
                                                                    backgroundColor: expandedItem?.id === item.id ? '#f5f0ff' : index % 2 === 0 ? '#ffffff' : '#f8f9fa',
                                                                    transition: 'all 0.2s'
                                                                }}
                                                                onMouseOver={(e) => {
                                                                    if (expandedItem?.id !== item.id && !editingItemId) {
                                                                        e.currentTarget.style.backgroundColor = '#e8e0f9';
                                                                    }
                                                                }}
                                                                onMouseOut={(e) => {
                                                                    if (expandedItem?.id !== item.id) {
                                                                        e.currentTarget.style.backgroundColor = index % 2 === 0 ? '#ffffff' : '#f8f9fa';
                                                                    }
                                                                }}
                                                            >
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {item.serial_number || index + 1}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {item.hs_code_label || item.hs_code || '-'}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {item.description || '-'}
                                                                </td>
                                                                <td onClick={(e) => e.stopPropagation()} style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
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
                                                                                menuPortalTarget={document.body}
                                                                                menuPosition="fixed"
                                                                                styles={{
                                                                                    control: (base) => ({
                                                                                        ...base,
                                                                                        minHeight: '32px',
                                                                                        fontSize: '0.875rem',
                                                                                        minWidth: '400px'
                                                                                    }),
                                                                                    valueContainer: (base) => ({
                                                                                        ...base,
                                                                                        flexWrap: 'wrap',
                                                                                        maxHeight: '100px',
                                                                                        overflow: 'auto'
                                                                                    }),
                                                                                    multiValue: (base) => ({
                                                                                        ...base,
                                                                                        maxWidth: '100%'
                                                                                    }),
                                                                                    multiValueLabel: (base) => ({
                                                                                        ...base,
                                                                                        whiteSpace: 'normal',
                                                                                        wordBreak: 'break-word',
                                                                                        padding: '3px 6px'
                                                                                    }),
                                                                                    menuPortal: (base) => ({
                                                                                        ...base,
                                                                                        zIndex: 9999
                                                                                    }),
                                                                                    menu: (base) => ({
                                                                                        ...base,
                                                                                        minWidth: '400px',
                                                                                        width: 'max-content'
                                                                                    }),
                                                                                    option: (base) => ({
                                                                                        ...base,
                                                                                        whiteSpace: 'nowrap'
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
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {parseFloat(item.quantity || 0).toFixed(2)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {parseFloat(item.allotted_quantity || 0).toFixed(2)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {parseFloat(item.debited_quantity || 0).toFixed(2)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {parseFloat(item.available_quantity || 0).toFixed(2)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {parseFloat(item.cif_fc || 0).toFixed(2)}
                                                                </td>
                                                                <td style={{ padding: '0.6rem', fontSize: '0.875rem', border: 'none', borderBottom: '1px solid #e9ecef' }}>
                                                                    {parseFloat(item.balance_cif_fc || 0).toFixed(2)}
                                                                </td>
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
                    <div className="modal-footer" style={{
                        backgroundColor: '#f8f9fa',
                        borderTop: '1px solid #dee2e6',
                        padding: '1rem 2rem',
                        borderBottomLeftRadius: '12px',
                        borderBottomRightRadius: '12px'
                    }}>
                        <button
                            type="button"
                            className="btn"
                            onClick={onHide}
                            style={{
                                backgroundColor: '#6c757d',
                                color: 'white',
                                borderRadius: '6px',
                                padding: '0.5rem 1.5rem',
                                fontWeight: '500',
                                border: 'none',
                                transition: 'all 0.3s'
                            }}
                            onMouseOver={(e) => {
                                e.target.style.backgroundColor = '#5a6268';
                                e.target.style.transform = 'translateY(-2px)';
                                e.target.style.boxShadow = '0 4px 12px rgba(0,0,0,0.15)';
                            }}
                            onMouseOut={(e) => {
                                e.target.style.backgroundColor = '#6c757d';
                                e.target.style.transform = 'translateY(0)';
                                e.target.style.boxShadow = 'none';
                            }}
                        >
                            <i className="bi bi-x-circle me-2"></i>
                            Close
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
