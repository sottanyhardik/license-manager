import {useEffect, useState} from "react";
import {useParams, useNavigate} from "react-router-dom";
import api from "../api/axios";
import TransferLetterForm from "../components/TransferLetterForm";

export default function TradeTransferLetter({ tradeId: propId, isModal = false, onClose }) {
    const {id: paramId} = useParams();
    const navigate = useNavigate();

    // Use prop ID if provided (for modal), otherwise use URL param (for page)
    const id = propId || paramId;

    const [trade, setTrade] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    useEffect(() => {
        fetchTrade();
    }, [id]);

    const fetchTrade = async () => {
        try {
            const {data} = await api.get(`/trades/${id}/`);
            setTrade(data);
        } catch (err) {
            setError("Failed to load Trade details");
        } finally {
            setLoading(false);
        }
    };

    if (loading) return <div className="p-4">Loading...</div>;

    return (
        <div className="container-fluid p-4">
            {!isModal && (
                <div className="d-flex justify-content-between align-items-center mb-4">
                    <h2>Generate Transfer Letter - Trade: {trade?.invoice_number || trade?.id}</h2>
                    <button
                        className="btn btn-secondary"
                        onClick={() => navigate('/trades')}
                    >
                        Back to Trade List
                    </button>
                </div>
            )}

            {error && <div className="alert alert-danger">{error}</div>}
            {success && <div className="alert alert-success">{success}</div>}

            {trade && (
                <>
                    {/* Trade Details */}
                    <div className="card mb-4">
                        <div className="card-body">
                            <h5 className="card-title mb-3">Trade Details</h5>
                            <div className="row">
                                <div className="col-md-3">
                                    <small className="text-muted">Direction</small>
                                    <div><strong>{trade.direction}</strong></div>
                                </div>
                                <div className="col-md-3">
                                    <small className="text-muted">Invoice Number</small>
                                    <div><strong>{trade.invoice_number || '-'}</strong></div>
                                </div>
                                <div className="col-md-3">
                                    <small className="text-muted">Invoice Date</small>
                                    <div><strong>{trade.invoice_date}</strong></div>
                                </div>
                                <div className="col-md-3">
                                    <small className="text-muted">Total Items</small>
                                    <div><strong>{trade.lines?.length || 0}</strong></div>
                                </div>
                            </div>
                            <div className="row mt-3">
                                <div className="col-md-6">
                                    <small className="text-muted">From Company</small>
                                    <div><strong>{trade.from_company_name || '-'}</strong></div>
                                </div>
                                <div className="col-md-6">
                                    <small className="text-muted">To Company</small>
                                    <div><strong>{trade.to_company_name || '-'}</strong></div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Transfer Letter Form */}
                    <TransferLetterForm
                        instanceId={id}
                        instanceType="trade"
                        instanceIdentifier={trade.invoice_number || trade.id}
                        items={trade.lines?.map(line => ({
                            id: line.id,
                            license_number: line.sr_number_label || '-',
                            cif_fc: line.cif_fc,
                            purchase_status: line.purchase_status || 'N/A'
                        })) || []}
                        onSuccess={(msg) => setSuccess(msg)}
                        onError={(msg) => setError(msg)}
                    />
                </>
            )}
        </div>
    );
}
