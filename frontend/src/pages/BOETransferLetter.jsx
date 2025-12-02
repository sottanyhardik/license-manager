import {useEffect, useState} from "react";
import {useParams, useNavigate} from "react-router-dom";
import api from "../api/axios";
import CreatableSelect from 'react-select/creatable';

export default function BOETransferLetter() {
    const {id} = useParams();
    const navigate = useNavigate();

    const [boe, setBoe] = useState(null);
    const [loading, setLoading] = useState(true);
    const [transferLetterData, setTransferLetterData] = useState({
        company: null,
        addressLine1: "",
        addressLine2: "",
        template: "",
        cifEdits: {}
    });
    const [companyOptions, setCompanyOptions] = useState([]);
    const [transferLetters, setTransferLetters] = useState([]);
    const [generatingTL, setGeneratingTL] = useState(false);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    useEffect(() => {
        fetchBOE();
        fetchTransferLetters();
    }, [id]);

    const fetchBOE = async () => {
        try {
            const {data} = await api.get(`/bill-of-entries/${id}/`);
            setBoe(data);

            // Pre-fill address from company if available
            if (data.company) {
                setTransferLetterData(prev => ({
                    ...prev,
                    addressLine1: data.company.address_line_1 || "",
                    addressLine2: data.company.address_line_2 || ""
                }));
            }
        } catch (err) {
            setError("Failed to load BOE details");
        } finally {
            setLoading(false);
        }
    };

    const fetchTransferLetters = async () => {
        try {
            const {data} = await api.get('/masters/transfer-letters/');
            setTransferLetters(data.results || data || []);
        } catch (err) {
            console.error("Failed to load transfer letters:", err);
        }
    };

    const handleGenerateTransferLetter = async () => {
        if (!transferLetterData.template) {
            setError("Please select a transfer letter template");
            return;
        }

        // Get company name from company object
        const finalCompanyName = transferLetterData.company?.label || '';

        if (!finalCompanyName.trim()) {
            setError("Please select or enter a company name");
            return;
        }

        setGeneratingTL(true);
        setError("");
        setSuccess("");

        // Debug current state
        console.log('BOE transferLetterData state:', transferLetterData);

        // Prepare request data
        const requestData = {
            company_name: finalCompanyName.trim(),
            address_line1: transferLetterData.addressLine1.trim(),
            address_line2: transferLetterData.addressLine2.trim(),
            template_id: transferLetterData.template,
            cif_edits: transferLetterData.cifEdits || {}
        };

        // Debug logging
        console.log('BOE Transfer Letter Request Data:', requestData);
        console.log('Company object:', transferLetterData.company);
        console.log('Final company name used:', finalCompanyName);

        try {
            const response = await api.post(`/bill-of-entries/${id}/generate-transfer-letter/`, requestData, {
                responseType: 'blob'
            });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `TransferLetter_BOE_${boe?.bill_of_entry_number || id}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            setSuccess("Transfer letter generated successfully");
        } catch (err) {
            setError(err.response?.data?.error || "Failed to generate transfer letter");
        } finally {
            setGeneratingTL(false);
        }
    };

    const handleCifEdit = (itemId, value) => {
        setTransferLetterData(prev => ({
            ...prev,
            cifEdits: {
                ...prev.cifEdits,
                [itemId]: value
            }
        }));
    };

    const loadCompanyOptions = async (inputValue) => {
        try {
            const {data} = await api.get(`/masters/companies/?search=${inputValue}`);
            const results = data.results || data || [];
            return results.map(company => ({
                value: company.id,
                label: company.name,
                ...company
            }));
        } catch (err) {
            console.error("Failed to load companies:", err);
            return [];
        }
    };

    const handleCompanyChange = async (selectedCompany, actionMeta) => {
        console.log('Company changed:', selectedCompany, 'Action:', actionMeta);

        // Set the company
        setTransferLetterData(prev => ({
            ...prev,
            company: selectedCompany
        }));

        // Fetch and populate address if company is selected from existing options (not created)
        if (selectedCompany && selectedCompany.value && actionMeta.action !== 'create-option') {
            try {
                const {data} = await api.get(`/masters/companies/${selectedCompany.value}/`);
                console.log('Company details fetched:', data);

                setTransferLetterData(prev => ({
                    ...prev,
                    company: selectedCompany,
                    addressLine1: data.address_line_1 || "",
                    addressLine2: data.address_line_2 || ""
                }));
            } catch (err) {
                console.error("Failed to fetch company details:", err);
            }
        } else if (!selectedCompany) {
            // Clear everything when company is cleared
            setTransferLetterData(prev => ({
                ...prev,
                company: null,
                addressLine1: "",
                addressLine2: ""
            }));
        }
    };

    if (loading) return <div className="p-4">Loading...</div>;

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>Generate Transfer Letter - BOE: {boe?.bill_of_entry_number}</h2>
                <button
                    className="btn btn-secondary"
                    onClick={() => navigate('/bill-of-entries')}
                >
                    Back to BOE List
                </button>
            </div>

            {error && <div className="alert alert-danger">{error}</div>}
            {success && <div className="alert alert-success">{success}</div>}

            {boe && (
                <>
                    {/* BOE Details */}
                    <div className="card mb-4">
                        <div className="card-body">
                            <h5 className="card-title mb-3">BOE Details</h5>
                            <div className="row">
                                <div className="col-md-3">
                                    <small className="text-muted">BOE Number</small>
                                    <div><strong>{boe.bill_of_entry_number}</strong></div>
                                </div>
                                <div className="col-md-3">
                                    <small className="text-muted">BOE Date</small>
                                    <div><strong>{boe.bill_of_entry_date}</strong></div>
                                </div>
                                <div className="col-md-3">
                                    <small className="text-muted">Company</small>
                                    <div><strong>{boe.company_name || boe.company?.name}</strong></div>
                                </div>
                                <div className="col-md-3">
                                    <small className="text-muted">Total Items</small>
                                    <div><strong>{boe.item_details?.length || 0}</strong></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Transfer Letter Form */}
                    <div className="card mb-4">
                        <div className="card-body">
                            <h5 className="mb-3">Transfer Letter Details</h5>
                            <div className="row mb-3">
                                <div className="col-md-4">
                                    <label className="form-label">Company <span className="text-danger">*</span></label>
                                    <CreatableSelect
                                        value={transferLetterData.company}
                                        onChange={handleCompanyChange}
                                        onInputChange={(inputValue) => {
                                            if (inputValue.length >= 2) {
                                                loadCompanyOptions(inputValue).then(options => setCompanyOptions(options));
                                            }
                                        }}
                                        options={companyOptions}
                                        placeholder="Type to search or enter company name..."
                                        isClearable={true}
                                        formatCreateLabel={(inputValue) => `Use: "${inputValue}"`}
                                    />
                                    <small className="text-muted">Select from dropdown to auto-fill addresses, or type to create custom entry</small>
                                </div>
                                <div className="col-md-4">
                                    <label className="form-label">Address Line 1</label>
                                    <input
                                        type="text"
                                        className="form-control"
                                        value={transferLetterData.addressLine1}
                                        onChange={(e) => setTransferLetterData(prev => ({...prev, addressLine1: e.target.value}))}
                                        placeholder="Enter address line 1"
                                    />
                                </div>
                                <div className="col-md-4">
                                    <label className="form-label">Address Line 2</label>
                                    <input
                                        type="text"
                                        className="form-control"
                                        value={transferLetterData.addressLine2}
                                        onChange={(e) => setTransferLetterData(prev => ({...prev, addressLine2: e.target.value}))}
                                        placeholder="Enter address line 2"
                                    />
                                </div>
                            </div>
                            <div className="row mb-3">
                                <div className="col-md-6">
                                    <label className="form-label">Template</label>
                                    <select
                                        className="form-select"
                                        value={transferLetterData.template}
                                        onChange={(e) => setTransferLetterData(prev => ({...prev, template: e.target.value}))}
                                    >
                                        <option value="">— Select Transfer Letter Template —</option>
                                        {transferLetters.map((tl) => (
                                            <option key={tl.id} value={tl.id}>{tl.name}</option>
                                        ))}
                                    </select>
                                </div>
                            </div>

                            {/* Edit CIF (FC) per SR */}
                            {boe.item_details && boe.item_details.length > 0 && (
                                <div className="mb-3">
                                    <h6>Edit CIF (FC) per Item</h6>
                                    <div className="table-responsive">
                                        <table className="table table-sm table-bordered">
                                            <thead className="table-light">
                                            <tr>
                                                <th>#</th>
                                                <th>License Number</th>
                                                <th>CIF FC (editable)</th>
                                            </tr>
                                            </thead>
                                            <tbody>
                                            {boe.item_details.map((detail, idx) => (
                                                <tr key={detail.id}>
                                                    <td>{idx + 1}</td>
                                                    <td>{detail.license?.license_number || detail.license_number || '-'}</td>
                                                    <td>
                                                        <input
                                                            type="number"
                                                            className="form-control form-control-sm"
                                                            value={transferLetterData.cifEdits[detail.id] !== undefined ? transferLetterData.cifEdits[detail.id] : parseFloat(detail.cif_fc || 0).toFixed(2)}
                                                            onChange={(e) => handleCifEdit(detail.id, e.target.value)}
                                                            step="0.01"
                                                        />
                                                    </td>
                                                </tr>
                                            ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}

                            {(!boe.item_details || boe.item_details.length === 0) && (
                                <div className="alert alert-warning">
                                    No items found in this BOE. Please add items first.
                                </div>
                            )}

                            <div className="d-flex justify-content-end">
                                <button
                                    className="btn btn-warning"
                                    onClick={handleGenerateTransferLetter}
                                    disabled={generatingTL || !transferLetterData.template || !boe.item_details || boe.item_details.length === 0}
                                >
                                    {generatingTL ? (
                                        <>
                                            <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                            Generating...
                                        </>
                                    ) : (
                                        <>
                                            <i className="bi bi-file-earmark-text me-2"></i>
                                            Generate Transfer Letter
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
