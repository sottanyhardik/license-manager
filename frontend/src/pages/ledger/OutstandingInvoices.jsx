import {useEffect, useState} from "react";
import {toast} from 'react-toastify';
import api from "../../api/axios";

export default function OutstandingInvoices() {
    const [outstandingData, setOutstandingData] = useState(null);
    const [loading, setLoading] = useState(false);
    const [invoiceType, setInvoiceType] = useState(''); // '' = all, 'receivable', 'payable'
    const [asOfDate, setAsOfDate] = useState(new Date().toISOString().split('T')[0]);

    const fetchOutstandingInvoices = async () => {
        setLoading(true);
        try {
            let url = `/ledger/reports/outstanding-invoices/?as_of_date=${asOfDate}`;
            if (invoiceType) url += `&type=${invoiceType}`;
            const response = await api.get(url);
            setOutstandingData(response.data);
            setLoading(false);
        } catch (error) {
            toast.error('Failed to fetch outstanding invoices');
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchOutstandingInvoices();
    }, []);

    const formatCurrency = (amount) => {
        if (!amount && amount !== 0) return '₹0.00';
        return `₹${parseFloat(amount).toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    };

    const getDaysOverdue = (dueDate) => {
        if (!dueDate) return 0;
        const today = new Date(asOfDate);
        const due = new Date(dueDate);
        const diffTime = today - due;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        return diffDays;
    };

    const getOverdueClass = (days) => {
        if (days <= 0) return 'text-success';
        if (days <= 30) return 'text-warning';
        if (days <= 60) return 'text-danger';
        return 'text-danger fw-bold';
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
                <h2><i className="bi bi-cash-stack me-2"></i>Outstanding Invoices</h2>
                <div className="d-flex gap-2">
                    <select
                        className="form-select"
                        value={invoiceType}
                        onChange={(e) => setInvoiceType(e.target.value)}
                        style={{width: '200px'}}
                    >
                        <option value="">All Invoices</option>
                        <option value="receivable">Receivables (Due from Customers)</option>
                        <option value="payable">Payables (Due to Suppliers)</option>
                    </select>
                    <input
                        type="date"
                        className="form-control"
                        value={asOfDate}
                        onChange={(e) => setAsOfDate(e.target.value)}
                        style={{width: '200px'}}
                    />
                    <button className="btn btn-primary" onClick={fetchOutstandingInvoices}>
                        <i className="bi bi-arrow-clockwise me-2"></i>Refresh
                    </button>
                    <button className="btn btn-secondary" onClick={printReport}>
                        <i className="bi bi-printer me-2"></i>Print
                    </button>
                </div>
            </div>

            {outstandingData && (
                <>
                    {/* Summary Cards */}
                    <div className="row mb-4">
                        <div className="col-md-4">
                            <div className="card bg-primary text-white">
                                <div className="card-body">
                                    <h6>Total Outstanding</h6>
                                    <h3>{formatCurrency(outstandingData.total_outstanding)}</h3>
                                </div>
                            </div>
                        </div>
                        <div className="col-md-4">
                            <div className="card bg-success text-white">
                                <div className="card-body">
                                    <h6>Receivables (Due from Customers)</h6>
                                    <h3>{formatCurrency(outstandingData.total_receivables)}</h3>
                                </div>
                            </div>
                        </div>
                        <div className="col-md-4">
                            <div className="card bg-danger text-white">
                                <div className="card-body">
                                    <h6>Payables (Due to Suppliers)</h6>
                                    <h3>{formatCurrency(outstandingData.total_payables)}</h3>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="card">
                        <div className="card-body">
                            <div className="text-center mb-4 print-header">
                                <h3>Outstanding Invoices Report</h3>
                                <p className="text-muted">As of {new Date(asOfDate).toLocaleDateString('en-GB')}</p>
                            </div>

                            <div className="table-responsive">
                                <table className="table table-hover">
                                    <thead className="table-dark">
                                        <tr>
                                            <th>Type</th>
                                            <th>Party Name</th>
                                            <th>Invoice Number</th>
                                            <th>Date</th>
                                            <th>Due Date</th>
                                            <th className="text-end">Amount</th>
                                            <th className="text-end">Paid</th>
                                            <th className="text-end">Outstanding</th>
                                            <th className="text-center">Days</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {outstandingData.invoices?.map((invoice, index) => {
                                            const daysOverdue = getDaysOverdue(invoice.due_date);
                                            return (
                                                <tr key={index}>
                                                    <td>
                                                        <span className={`badge ${
                                                            invoice.type === 'RECEIVABLE' ? 'bg-success' : 'bg-danger'
                                                        }`}>
                                                            {invoice.type}
                                                        </span>
                                                    </td>
                                                    <td><strong>{invoice.party_name}</strong></td>
                                                    <td><code>{invoice.invoice_number}</code></td>
                                                    <td>{new Date(invoice.invoice_date).toLocaleDateString('en-GB')}</td>
                                                    <td>
                                                        {invoice.due_date
                                                            ? new Date(invoice.due_date).toLocaleDateString('en-GB')
                                                            : '-'
                                                        }
                                                    </td>
                                                    <td className="text-end">{formatCurrency(invoice.total_amount)}</td>
                                                    <td className="text-end">{formatCurrency(invoice.paid_amount)}</td>
                                                    <td className="text-end">
                                                        <strong>{formatCurrency(invoice.outstanding_amount)}</strong>
                                                    </td>
                                                    <td className={`text-center ${getOverdueClass(daysOverdue)}`}>
                                                        {daysOverdue > 0 ? (
                                                            <span>
                                                                {daysOverdue} days
                                                                <i className="bi bi-exclamation-circle ms-1"></i>
                                                            </span>
                                                        ) : daysOverdue === 0 ? (
                                                            <span className="text-warning">Due Today</span>
                                                        ) : (
                                                            <span>{Math.abs(daysOverdue)} days left</span>
                                                        )}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                        {outstandingData.invoices?.length === 0 && (
                                            <tr>
                                                <td colSpan="9" className="text-center text-muted py-4">
                                                    No outstanding invoices found
                                                </td>
                                            </tr>
                                        )}
                                    </tbody>
                                    <tfoot className="table-light">
                                        <tr>
                                            <th colSpan="5" className="text-end">Total:</th>
                                            <th className="text-end">
                                                {formatCurrency(outstandingData.invoices?.reduce((sum, inv) => sum + parseFloat(inv.total_amount), 0))}
                                            </th>
                                            <th className="text-end">
                                                {formatCurrency(outstandingData.invoices?.reduce((sum, inv) => sum + parseFloat(inv.paid_amount), 0))}
                                            </th>
                                            <th className="text-end">
                                                {formatCurrency(outstandingData.invoices?.reduce((sum, inv) => sum + parseFloat(inv.outstanding_amount), 0))}
                                            </th>
                                            <th></th>
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>

                            {/* Aging Analysis */}
                            <div className="mt-4">
                                <h5>Aging Analysis</h5>
                                <div className="row">
                                    <div className="col-md-3">
                                        <div className="card bg-success text-white">
                                            <div className="card-body">
                                                <h6>Current (Not Due)</h6>
                                                <h4>{formatCurrency(outstandingData.aging?.current || 0)}</h4>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="col-md-3">
                                        <div className="card bg-info text-white">
                                            <div className="card-body">
                                                <h6>1-30 Days</h6>
                                                <h4>{formatCurrency(outstandingData.aging?.days_1_30 || 0)}</h4>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="col-md-3">
                                        <div className="card bg-warning text-white">
                                            <div className="card-body">
                                                <h6>31-60 Days</h6>
                                                <h4>{formatCurrency(outstandingData.aging?.days_31_60 || 0)}</h4>
                                            </div>
                                        </div>
                                    </div>
                                    <div className="col-md-3">
                                        <div className="card bg-danger text-white">
                                            <div className="card-body">
                                                <h6>Over 60 Days</h6>
                                                <h4>{formatCurrency(outstandingData.aging?.over_60_days || 0)}</h4>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </>
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
