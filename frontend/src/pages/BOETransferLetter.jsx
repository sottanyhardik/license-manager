import {useEffect, useState} from "react";
import {useParams, useNavigate} from "react-router-dom";
import api from "../api/axios";
import TransferLetterForm from "../components/TransferLetterForm";

export default function BOETransferLetter() {
    const {id} = useParams();
    const navigate = useNavigate();

    const [boe, setBoe] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");

    useEffect(() => {
        fetchBOE();
    }, [id]);

    const fetchBOE = async () => {
        try {
            const {data} = await api.get(`/bill-of-entries/${id}/`);
            setBoe(data);
        } catch (err) {
            setError("Failed to load BOE details");
        } finally {
            setLoading(false);
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
                    <TransferLetterForm
                        instanceId={id}
                        instanceType="boe"
                        items={boe.item_details?.map(detail => ({
                            id: detail.id,
                            license_number: detail.license?.license_number || detail.license_number || '-',
                            cif_fc: detail.cif_fc,
                            purchase_status: detail.purchase_status
                        })) || []}
                        onSuccess={(msg) => setSuccess(msg)}
                        onError={(msg) => setError(msg)}
                    />
                </>
            )}
        </div>
    );
}
