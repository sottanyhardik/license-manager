import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function BalanceSheet() {
    const [balanceSheet, setBalanceSheet] = useState(null);
    const [loading, setLoading] = useState(false);
    const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0]);

    const fetchBalanceSheet = async () => {
        setLoading(true);
        try {
            const response = await api.get(`/chart-of-accounts/balance_sheet/?as_of_date=${asOfDate}`);
            setBalanceSheet(response.data);
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch balance sheet');
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchBalanceSheet();
    }, []);

    const formatCurrency = (amount) => {
        if (!amount && amount !== 0) return '₹0.00';
        return `₹${parseFloat(amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    };

    const printReport = () => {
        window.print();
    };

    if (loading) {
        return <div className="container mt-4"><div className="spinner-border" role="status"></div></div>;
    }

    return (
        <div className="container-fluid mt-4">
            <div className="d-flex justify-content-between align-items-center mb-4 no-print">
                <h2><i className="bi bi-bar-chart me-2"></i>Balance Sheet</h2>
                <div className="d-flex gap-2">
                    <input
                        type="date"
                        className="form-control"
                        value={asOfDate}
                        onChange={(e) => setAsOfDate(e.target.value)}
                        style={{width: '200px'}}
                    />
                    <button className="btn btn-primary" onClick={fetchBalanceSheet}>
                        <i className="bi bi-arrow-clockwise me-2"></i>Refresh
                    </button>
                    <button className="btn btn-secondary" onClick={printReport}>
                        <i className="bi bi-printer me-2"></i>Print
                    </button>
                </div>
            </div>

            {balanceSheet && (
                <div className="card">
                    <div className="card-body">
                        <div className="text-center mb-4 print-header">
                            <h3>Balance Sheet</h3>
                            <p className="text-muted">As of {new Date(asOfDate).toLocaleDateString('en-GB')}</p>
                        </div>

                        <div className="row">
                            {/* Assets Column */}
                            <div className="col-md-6">
                                <h5 className="bg-primary text-white p-2">ASSETS</h5>
                                <table className="table table-sm">
                                    <tbody>
                                        {balanceSheet.assets?.map((account, index) => (
                                            <tr key={index}>
                                                <td>{account.code}</td>
                                                <td>{account.name}</td>
                                                <td className="text-end">{formatCurrency(account.balance)}</td>
                                            </tr>
                                        ))}
                                        {balanceSheet.assets?.length === 0 && (
                                            <tr>
                                                <td colSpan="3" className="text-center text-muted">No asset accounts</td>
                                            </tr>
                                        )}
                                        <tr className="table-dark fw-bold">
                                            <td colSpan="2">Total Assets</td>
                                            <td className="text-end">{formatCurrency(balanceSheet.total_assets)}</td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>

                            {/* Liabilities & Equity Column */}
                            <div className="col-md-6">
                                <h5 className="bg-danger text-white p-2">LIABILITIES</h5>
                                <table className="table table-sm">
                                    <tbody>
                                        {balanceSheet.liabilities?.map((account, index) => (
                                            <tr key={index}>
                                                <td>{account.code}</td>
                                                <td>{account.name}</td>
                                                <td className="text-end">{formatCurrency(account.balance)}</td>
                                            </tr>
                                        ))}
                                        {balanceSheet.liabilities?.length === 0 && (
                                            <tr>
                                                <td colSpan="3" className="text-center text-muted">No liability accounts</td>
                                            </tr>
                                        )}
                                        <tr className="table-secondary fw-bold">
                                            <td colSpan="2">Total Liabilities</td>
                                            <td className="text-end">{formatCurrency(balanceSheet.total_liabilities)}</td>
                                        </tr>
                                    </tbody>
                                </table>

                                <h5 className="bg-success text-white p-2 mt-3">EQUITY</h5>
                                <table className="table table-sm">
                                    <tbody>
                                        {balanceSheet.equity?.map((account, index) => (
                                            <tr key={index}>
                                                <td>{account.code}</td>
                                                <td>{account.name}</td>
                                                <td className="text-end">{formatCurrency(account.balance)}</td>
                                            </tr>
                                        ))}
                                        {balanceSheet.equity?.length === 0 && (
                                            <tr>
                                                <td colSpan="3" className="text-center text-muted">No equity accounts</td>
                                            </tr>
                                        )}
                                        <tr className="table-secondary fw-bold">
                                            <td colSpan="2">Total Equity</td>
                                            <td className="text-end">{formatCurrency(balanceSheet.total_equity)}</td>
                                        </tr>
                                    </tbody>
                                </table>

                                <table className="table table-sm mt-3">
                                    <tbody>
                                        <tr className="table-dark fw-bold">
                                            <td colSpan="2">Total Liabilities & Equity</td>
                                            <td className="text-end">
                                                {formatCurrency(balanceSheet.total_liabilities_and_equity)}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {/* Balance Check */}
                        <div className="mt-4">
                            <div className={`alert ${
                                Math.abs(balanceSheet.total_assets - balanceSheet.total_liabilities_and_equity) < 0.01
                                ? 'alert-success'
                                : 'alert-danger'
                            }`}>
                                <strong>Balance Check:</strong> Assets = Liabilities + Equity
                                <div className="mt-2">
                                    {formatCurrency(balanceSheet.total_assets)} = {formatCurrency(balanceSheet.total_liabilities_and_equity)}
                                </div>
                                {Math.abs(balanceSheet.total_assets - balanceSheet.total_liabilities_and_equity) < 0.01 ? (
                                    <div className="mt-2">
                                        <i className="bi bi-check-circle me-2"></i>
                                        Balance Sheet is balanced
                                    </div>
                                ) : (
                                    <div className="mt-2">
                                        <i className="bi bi-exclamation-triangle me-2"></i>
                                        Balance Sheet is not balanced! Difference: {
                                            formatCurrency(Math.abs(balanceSheet.total_assets - balanceSheet.total_liabilities_and_equity))
                                        }
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            )}

            <style>{`
                @media print {
                    .no-print {
                        display: none !important;
                    }
                    .card {
                        border: none !important;
                        box-shadow: none !important;
                    }
                    .print-header {
                        margin-bottom: 30px;
                    }
                }
            `}</style>
        </div>
    );
}
