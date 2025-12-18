import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function ProfitLoss() {
    const [profitLoss, setProfitLoss] = useState(null);
    const [loading, setLoading] = useState(false);
    const [dateFrom, setDateFrom] = useState(new Date(new Date().getFullYear(), 3, 1).toISOString().split('T')[0]); // April 1st
    const [dateTo, setDateTo] = useState(new Date().toISOString().split('T')[0]);

    const fetchProfitLoss = async () => {
        setLoading(true);
        try {
            const response = await api.get(`/chart-of-accounts/profit_loss/?date_from=${dateFrom}&date_to=${dateTo}`);
            setProfitLoss(response.data);
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch profit & loss statement');
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchProfitLoss();
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
                <h2><i className="bi bi-graph-up me-2"></i>Profit & Loss Statement</h2>
                <div className="d-flex gap-2">
                    <input
                        type="date"
                        className="form-control"
                        value={dateFrom}
                        onChange={(e) => setDateFrom(e.target.value)}
                        style={{width: '180px'}}
                    />
                    <span className="align-self-center">to</span>
                    <input
                        type="date"
                        className="form-control"
                        value={dateTo}
                        onChange={(e) => setDateTo(e.target.value)}
                        style={{width: '180px'}}
                    />
                    <button className="btn btn-primary" onClick={fetchProfitLoss}>
                        <i className="bi bi-arrow-clockwise me-2"></i>Refresh
                    </button>
                    <button className="btn btn-secondary" onClick={printReport}>
                        <i className="bi bi-printer me-2"></i>Print
                    </button>
                </div>
            </div>

            {profitLoss && (
                <div className="card">
                    <div className="card-body">
                        <div className="text-center mb-4 print-header">
                            <h3>Profit & Loss Statement</h3>
                            <p className="text-muted">
                                From {new Date(dateFrom).toLocaleDateString('en-GB')} to {new Date(dateTo).toLocaleDateString('en-GB')}
                            </p>
                        </div>

                        {/* Revenue Section */}
                        <div className="mb-4">
                            <h5 className="bg-success text-white p-2">REVENUE / INCOME</h5>
                            <table className="table table-sm">
                                <tbody>
                                    {profitLoss.revenue?.map((account, index) => (
                                        <tr key={index}>
                                            <td style={{width: '15%'}}>{account.code}</td>
                                            <td style={{width: '60%'}}>{account.name}</td>
                                            <td className="text-end" style={{width: '25%'}}>
                                                {formatCurrency(account.balance)}
                                            </td>
                                        </tr>
                                    ))}
                                    {profitLoss.revenue?.length === 0 && (
                                        <tr>
                                            <td colSpan="3" className="text-center text-muted">No revenue accounts</td>
                                        </tr>
                                    )}
                                    <tr className="table-success fw-bold">
                                        <td colSpan="2">Total Revenue</td>
                                        <td className="text-end">{formatCurrency(profitLoss.total_revenue)}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        {/* Expense Section */}
                        <div className="mb-4">
                            <h5 className="bg-danger text-white p-2">EXPENSES</h5>
                            <table className="table table-sm">
                                <tbody>
                                    {profitLoss.expenses?.map((account, index) => (
                                        <tr key={index}>
                                            <td style={{width: '15%'}}>{account.code}</td>
                                            <td style={{width: '60%'}}>{account.name}</td>
                                            <td className="text-end" style={{width: '25%'}}>
                                                {formatCurrency(account.balance)}
                                            </td>
                                        </tr>
                                    ))}
                                    {profitLoss.expenses?.length === 0 && (
                                        <tr>
                                            <td colSpan="3" className="text-center text-muted">No expense accounts</td>
                                        </tr>
                                    )}
                                    <tr className="table-danger fw-bold">
                                        <td colSpan="2">Total Expenses</td>
                                        <td className="text-end">{formatCurrency(profitLoss.total_expenses)}</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        {/* Net Profit/Loss */}
                        <div className="card bg-light">
                            <div className="card-body">
                                <div className="row">
                                    <div className="col-md-6">
                                        <h5>Total Revenue:</h5>
                                        <div className="fs-4 text-success">{formatCurrency(profitLoss.total_revenue)}</div>
                                    </div>
                                    <div className="col-md-6">
                                        <h5>Total Expenses:</h5>
                                        <div className="fs-4 text-danger">{formatCurrency(profitLoss.total_expenses)}</div>
                                    </div>
                                </div>
                                <hr />
                                <div className="text-center">
                                    <h4>
                                        {profitLoss.net_profit >= 0 ? 'Net Profit' : 'Net Loss'}
                                    </h4>
                                    <div className={`display-6 fw-bold ${profitLoss.net_profit >= 0 ? 'text-success' : 'text-danger'}`}>
                                        {formatCurrency(Math.abs(profitLoss.net_profit))}
                                    </div>
                                    {profitLoss.net_profit >= 0 ? (
                                        <div className="mt-2 text-success">
                                            <i className="bi bi-arrow-up-circle me-2"></i>
                                            Company is profitable
                                        </div>
                                    ) : (
                                        <div className="mt-2 text-danger">
                                            <i className="bi bi-arrow-down-circle me-2"></i>
                                            Company is in loss
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>

                        {/* Margin Calculation */}
                        {profitLoss.total_revenue > 0 && (
                            <div className="alert alert-info mt-3">
                                <strong>Profit Margin:</strong>{' '}
                                {((profitLoss.net_profit / profitLoss.total_revenue) * 100).toFixed(2)}%
                            </div>
                        )}
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
