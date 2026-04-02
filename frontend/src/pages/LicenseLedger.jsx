import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { formatDate } from '../utils/dateFormatter';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

export default function LicenseLedger() {
    const navigate = useNavigate();
    const [licenses, setLicenses] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [exportingPdf, setExportingPdf] = useState(false);
    const [filters, setFilters] = useState({
        license_type: 'ALL',
        min_balance: '',
        search: '',
        active_only: true,
        ordering: '-license_date',
        purchase_date_from: '',
        purchase_date_to: ''
    });

    const licenseTypeOptions = [
        { value: 'ALL', label: 'All Licenses', icon: 'bi-list-ul' },
        { value: 'DFIA', label: 'DFIA Only', icon: 'bi-globe' },
        { value: 'INCENTIVE', label: 'All Incentive', icon: 'bi-trophy' },
        { value: 'RODTEP', label: 'RODTEP', icon: 'bi-award' },
        { value: 'ROSTL', label: 'ROSTL', icon: 'bi-badge-tm' },
        { value: 'MEIS', label: 'MEIS', icon: 'bi-star' },
    ];

    useEffect(() => {
        fetchLedgerData();
        fetchSummary();
    }, [filters]);

    const fetchLedgerData = async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (filters.license_type) params.append('license_type', filters.license_type);
            if (filters.min_balance) params.append('min_balance', filters.min_balance);
            if (filters.search) params.append('search', filters.search);
            if (filters.ordering) params.append('ordering', filters.ordering);
            if (filters.purchase_date_from) params.append('purchase_date_from', filters.purchase_date_from);
            if (filters.purchase_date_to) params.append('purchase_date_to', filters.purchase_date_to);
            params.append('active_only', filters.active_only);

            const response = await api.get(`/license-ledger/?${params.toString()}`);

            // Handle multiple response formats
            const data = response.data;
            if (Array.isArray(data)) {
                // Direct array
                setLicenses(data);
            } else if (data && Array.isArray(data.results)) {
                // DRF paginated response: {count, next, previous, results}
                setLicenses(data.results);
            } else if (data && Array.isArray(data.licenses)) {
                // Custom format: {licenses}
                setLicenses(data.licenses);
            } else {
                setLicenses([]);
            }
        } catch (error) {
            console.error('Error fetching ledger data:', error);
            setLicenses([]);
        } finally {
            setLoading(false);
        }
    };

    const fetchSummary = async () => {
        try {
            const response = await api.get('/license-ledger/summary/');
            setSummary(response.data);
        } catch (error) {
            console.error('Error fetching summary:', error);
        }
    };

    const handleFilterChange = (field, value) => {
        setFilters(prev => ({ ...prev, [field]: value }));
    };

    const formatCurrency = (value, currency) => {
        const formatted = formatIndianNumber(value, 2);
        return currency === 'USD' ? `$ ${formatted}` : `₹ ${formatted}`;
    };

    const getSoldStatusBadge = (status) => {
        const badges = {
            'NO': { bg: 'success', text: 'Available', icon: 'bi-check-circle' },
            'PARTIAL': { bg: 'warning', text: 'Partial', icon: 'bi-hourglass-split' },
            'YES': { bg: 'danger', text: 'Sold Out', icon: 'bi-x-circle' }
        };
        const badge = badges[status] || { bg: 'secondary', text: status, icon: 'bi-question-circle' };
        return (
            <span className={`badge bg-${badge.bg}`} style={{ fontSize: '0.8rem', fontWeight: '500' }}>
                <i className={`bi ${badge.icon} me-1`}></i>
                {badge.text}
            </span>
        );
    };

    const handleViewDetails = (license) => {
        navigate(`/license-ledger/${license.id}`, {
            state: { license_type: license.license_type }
        });
    };

    const handleCreateTrade = (license) => {
        navigate('/trades/new', {
            state: {
                license_type: license.license_type === 'DFIA' ? 'DFIA' : 'INCENTIVE',
                license_id: license.id,
                license_number: license.license_number
            }
        });
    };

    const formatLedgerDate = (dateStr) => {
        if (!dateStr) return '-';
        return formatDate(dateStr) || '-';
    };

    const formatLedgerCurrency = (value, currency = 'INR') => {
        if (!value && value !== 0) return '-';
        const symbol = currency === 'USD' ? '$' : '₹';
        return `${symbol}${formatIndianNumber(value, 2)}`;
    };

    const fetchAllLicensesForExport = async () => {
        const params = new URLSearchParams();
        if (filters.license_type) params.append('license_type', filters.license_type);
        if (filters.min_balance) params.append('min_balance', filters.min_balance);
        if (filters.search) params.append('search', filters.search);
        if (filters.ordering) params.append('ordering', filters.ordering);
        params.append('active_only', filters.active_only);

        let url = `/license-ledger/?${params.toString()}`;
        const allLicenses = [];

        while (url) {
            const response = await api.get(url);
            const data = response.data;

            if (Array.isArray(data)) {
                allLicenses.push(...data);
                break;
            }

            if (data && Array.isArray(data.results)) {
                allLicenses.push(...data.results);
                url = data.next || null;
                continue;
            }

            if (data && Array.isArray(data.licenses)) {
                allLicenses.push(...data.licenses);
                break;
            }

            break;
        }

        return allLicenses;
    };

    const addLicenseSectionToPdf = (doc, ledger, licenseIndex, totalLicenses) => {
        if (licenseIndex > 0) {
            doc.addPage();
        }

        const pageWidth = doc.internal.pageSize.getWidth();
        const isDFIA = ledger.license_type === 'DFIA';
        const currentBalance = ledger.available_balance || 0;
        const transactions = Array.isArray(ledger.transactions) ? ledger.transactions : [];

        doc.setFontSize(18);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(25, 42, 86);
        doc.text('LICENSE LEDGER STATEMENT', pageWidth / 2, 12, { align: 'center' });

        doc.setFontSize(9);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(100, 116, 139);
        doc.text(`License ${licenseIndex + 1} of ${totalLicenses}`, pageWidth / 2, 17, { align: 'center' });

        doc.setDrawColor(52, 73, 94);
        doc.setLineWidth(0.5);
        doc.line(14, 20, pageWidth - 14, 20);

        doc.setFillColor(247, 249, 252);
        doc.roundedRect(14, 24, pageWidth - 28, 23, 2, 2, 'F');
        doc.setDrawColor(223, 227, 234);
        doc.roundedRect(14, 24, pageWidth - 28, 23, 2, 2, 'S');

        doc.setFontSize(14);
        doc.setTextColor(31, 41, 55);
        doc.setFont('helvetica', 'bold');
        doc.text(ledger.license_number || '-', 18, 31);

        doc.setFillColor(58, 145, 167);
        doc.roundedRect(52, 26.5, 22, 7, 1.5, 1.5, 'F');
        doc.setTextColor(255, 255, 255);
        doc.setFontSize(8.5);
        doc.text(ledger.license_type || 'N/A', 63, 31.5, { align: 'center' });

        doc.setFontSize(9);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(108, 117, 125);
        doc.text('Exporter:', 18, 38.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(17, 24, 39);
        doc.text((ledger.exporter || 'N/A').slice(0, 45), 33, 38.5);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(108, 117, 125);
        doc.text('License Date:', 95, 38.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(17, 24, 39);
        doc.text(formatLedgerDate(ledger.license_date), 116, 38.5);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(108, 117, 125);
        doc.text('Expiry Date:', 18, 44.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(17, 24, 39);
        doc.text(formatLedgerDate(ledger.expiry_date), 33, 44.5);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(108, 117, 125);
        doc.text('Total Value:', 95, 44.5);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(37, 99, 235);
        doc.text(formatLedgerCurrency(ledger.total_value || 0, isDFIA ? 'USD' : 'INR'), 114, 44.5);

        doc.setFillColor(246, 248, 250);
        doc.roundedRect(pageWidth - 72, 26.5, 54, 17, 2, 2, 'F');
        doc.setDrawColor(223, 227, 234);
        doc.roundedRect(pageWidth - 72, 26.5, 54, 17, 2, 2, 'S');
        doc.setFont('helvetica', 'bold');
        doc.setFontSize(9);
        doc.setTextColor(108, 117, 125);
        doc.text('CURRENT BALANCE', pageWidth - 45, 32, { align: 'center' });
        doc.setFontSize(14);
        doc.setTextColor(currentBalance >= 0 ? 52 : 220, currentBalance >= 0 ? 168 : 53, currentBalance >= 0 ? 83 : 69);
        doc.text(formatLedgerCurrency(currentBalance, isDFIA ? 'USD' : 'INR'), pageWidth - 45, 39, { align: 'center' });

        const headers = isDFIA
            ? [['Date', 'Particulars', 'Items', 'CIF Dr', 'CIF Cr', 'Rate', 'Debit (₹)', 'Credit (₹)', 'Balance', 'P/L']]
            : [['Date', 'Particulars', 'Value Dr', 'Value Cr', 'Rate', 'Debit (₹)', 'Credit (₹)', 'Balance', 'P/L']];

        const bodyData = transactions.map((txn) => {
            const row = [
                formatLedgerDate(txn.date),
                txn.particular + (txn.invoice_number ? `\nInvoice: ${txn.invoice_number}` : ''),
            ];

            if (isDFIA) {
                row.push(
                    txn.items || '',
                    txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '-',
                    txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : '-'
                );
            } else {
                row.push(
                    txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '-',
                    txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : '-'
                );
            }

            row.push(
                txn.rate ? formatIndianNumber(txn.rate, 2) : '-',
                txn.debit_amount ? formatIndianNumber(txn.debit_amount, 2) : '-',
                txn.credit_amount ? formatIndianNumber(txn.credit_amount, 2) : '-',
                formatIndianNumber(txn.balance || 0, 2),
                txn.type === 'SALE' && txn.profit_loss ? `${txn.profit_loss >= 0 ? '+' : '-'} ${formatIndianNumber(Math.abs(txn.profit_loss), 2)}` : '-'
            );

            return row;
        });

        const totalDebit = transactions.reduce((sum, t) => sum + (parseFloat(t.debit_amount) || 0), 0);
        const totalCredit = transactions.reduce((sum, t) => sum + (parseFloat(t.credit_amount) || 0), 0);
        const totalPL = transactions
            .filter((t) => t.type === 'SALE')
            .reduce((acc, t) => parseFloat(t.profit_loss || acc), 0);

        const totalsRow = isDFIA
            ? ['', 'TOTAL', '', '', '', '', formatIndianNumber(totalDebit, 2), formatIndianNumber(totalCredit, 2), formatIndianNumber(currentBalance, 2), `${totalPL >= 0 ? '+' : '-'} ${formatIndianNumber(Math.abs(totalPL), 2)}`]
            : ['', 'TOTAL', '', '', '', formatIndianNumber(totalDebit, 2), formatIndianNumber(totalCredit, 2), formatIndianNumber(currentBalance, 2), `${totalPL >= 0 ? '+' : '-'} ${formatIndianNumber(Math.abs(totalPL), 2)}`];

        bodyData.push(totalsRow);

        autoTable(doc, {
            head: headers,
            body: bodyData,
            startY: 52,
            styles: {
                fontSize: 8,
                cellPadding: 2.5,
                lineColor: [224, 224, 224],
                lineWidth: 0.2,
                halign: 'right',
                font: 'helvetica',
                textColor: [44, 62, 80]
            },
            headStyles: {
                fillColor: [52, 73, 94],
                fontStyle: 'bold',
                textColor: [255, 255, 255],
                halign: 'center',
                fontSize: 8.5
            },
            columnStyles: isDFIA ? {
                0: { halign: 'center', cellWidth: 18 },
                1: { halign: 'left', cellWidth: 44 },
                2: { halign: 'left', cellWidth: 26 },
                3: { halign: 'right', cellWidth: 22 },
                4: { halign: 'right', cellWidth: 22 },
                5: { halign: 'right', cellWidth: 16 },
                6: { halign: 'right', cellWidth: 24 },
                7: { halign: 'right', cellWidth: 24 },
                8: { halign: 'right', cellWidth: 24 },
                9: { halign: 'right', cellWidth: 20 }
            } : {
                0: { halign: 'center', cellWidth: 18 },
                1: { halign: 'left', cellWidth: 60 },
                2: { halign: 'right', cellWidth: 22 },
                3: { halign: 'right', cellWidth: 22 },
                4: { halign: 'right', cellWidth: 16 },
                5: { halign: 'right', cellWidth: 24 },
                6: { halign: 'right', cellWidth: 24 },
                7: { halign: 'right', cellWidth: 24 },
                8: { halign: 'right', cellWidth: 20 }
            },
            alternateRowStyles: {
                fillColor: [250, 251, 252]
            },
            margin: { left: 14, right: 14 },
            didParseCell: (data) => {
                if (data.row.index === transactions.length) {
                    data.cell.styles.fillColor = [236, 240, 241];
                    data.cell.styles.fontStyle = 'bold';
                    data.cell.styles.textColor = [25, 42, 86];
                }
            }
        });

        const finalY = doc.lastAutoTable?.finalY || 52;
        const purchaseCount = transactions.filter((t) => ['PURCHASE', 'OPENING'].includes(t.type)).length;
        const salesCount = transactions.filter((t) => t.type === 'SALE').length;

        doc.setDrawColor(224, 224, 224);
        doc.line(14, finalY + 5, pageWidth - 14, finalY + 5);

        doc.setFontSize(8.5);
        doc.setTextColor(108, 117, 125);
        doc.setFont('helvetica', 'normal');
        doc.text(`Transactions: ${transactions.length}`, 14, finalY + 10);
        doc.text(`Purchases: ${purchaseCount}`, 54, finalY + 10);
        doc.text(`Sales: ${salesCount}`, 90, finalY + 10);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(totalPL >= 0 ? 52 : 220, totalPL >= 0 ? 168 : 53, totalPL >= 0 ? 83 : 69);
        doc.text(`Net P/L: ${totalPL >= 0 ? '+' : '-'} ₹${formatIndianNumber(Math.abs(totalPL), 2)}`, pageWidth - 14, finalY + 10, { align: 'right' });
    };

    const handleExportAllPdf = async (exportOptions = {}) => {
        try {
            setExportingPdf(true);

            // Build query params based on export options
            const params = new URLSearchParams();

            // Use custom options or current filters
            const exportFilters = {
                license_type: exportOptions.license_type || filters.license_type,
                min_balance: exportOptions.min_balance || filters.min_balance,
                search: exportOptions.search || filters.search,
                ordering: exportOptions.ordering || filters.ordering,
                active_only: exportOptions.active_only !== undefined ? exportOptions.active_only : filters.active_only,
                purchase_date_from: exportOptions.purchase_date_from || filters.purchase_date_from,
                purchase_date_to: exportOptions.purchase_date_to || filters.purchase_date_to
            };

            if (exportFilters.license_type) params.append('license_type', exportFilters.license_type);
            if (exportFilters.min_balance) params.append('min_balance', exportFilters.min_balance);
            if (exportFilters.search) params.append('search', exportFilters.search);
            if (exportFilters.ordering) params.append('ordering', exportFilters.ordering);
            if (exportFilters.purchase_date_from) params.append('purchase_date_from', exportFilters.purchase_date_from);
            if (exportFilters.purchase_date_to) params.append('purchase_date_to', exportFilters.purchase_date_to);
            params.append('active_only', exportFilters.active_only);

            // Use the new backend endpoint that generates PDF directly
            const response = await api.get(`/license-ledger/export/all/?${params.toString()}`, {
                responseType: 'blob'
            });

            // Create download link with descriptive filename
            const blob = new Blob([response.data], { type: 'application/pdf' });
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;

            // Generate filename based on options
            let filenamePart = 'All';
            if (exportOptions.license_type && exportOptions.license_type !== 'ALL') {
                filenamePart = exportOptions.license_type;
            }
            if (!exportFilters.active_only) {
                filenamePart += '_Including_Expired';
            }

            link.download = `License_Ledger_${filenamePart}_${new Date().toISOString().split('T')[0]}.pdf`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error exporting PDF:', error);
            window.alert('Failed to export PDF. Please try again.');
        } finally {
            setExportingPdf(false);
        }
    };

    const handleExportWithFilters = () => {
        handleExportAllPdf();
    };

    const handleExportAllActive = () => {
        handleExportAllPdf({ license_type: 'ALL', active_only: true, min_balance: '', search: '', ordering: '-license_date' });
    };

    const handleExportAllIncludingExpired = () => {
        handleExportAllPdf({ license_type: 'ALL', active_only: false, min_balance: '', search: '', ordering: '-license_date' });
    };

    const handleExportDFIAOnly = () => {
        handleExportAllPdf({ license_type: 'DFIA', active_only: true, min_balance: '', search: '', ordering: '-license_date' });
    };

    const handleExportIncentiveOnly = () => {
        handleExportAllPdf({ license_type: 'INCENTIVE', active_only: true, min_balance: '', search: '', ordering: '-license_date' });
    };

    const handleExportWithBalance = () => {
        handleExportAllPdf({ min_balance: '100', active_only: true, ordering: '-balance_value' });
    };

    const handleExportLastMonth = () => {
        const today = new Date();
        const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        const lastMonthEnd = new Date(today.getFullYear(), today.getMonth(), 0);
        handleExportAllPdf({
            purchase_date_from: lastMonth.toISOString().split('T')[0],
            purchase_date_to: lastMonthEnd.toISOString().split('T')[0],
            active_only: true,
            ordering: '-license_date'
        });
    };

    const handleExportThisMonth = () => {
        const today = new Date();
        const thisMonthStart = new Date(today.getFullYear(), today.getMonth(), 1);
        handleExportAllPdf({
            purchase_date_from: thisMonthStart.toISOString().split('T')[0],
            purchase_date_to: today.toISOString().split('T')[0],
            active_only: true,
            ordering: '-license_date'
        });
    };

    const handleExportLast3Months = () => {
        const today = new Date();
        const threeMonthsAgo = new Date(today.getFullYear(), today.getMonth() - 3, today.getDate());
        handleExportAllPdf({
            purchase_date_from: threeMonthsAgo.toISOString().split('T')[0],
            purchase_date_to: today.toISOString().split('T')[0],
            active_only: true,
            ordering: '-license_date'
        });
    };

    const handleExportThisYear = () => {
        const today = new Date();
        const yearStart = new Date(today.getFullYear(), 0, 1);
        handleExportAllPdf({
            purchase_date_from: yearStart.toISOString().split('T')[0],
            purchase_date_to: today.toISOString().split('T')[0],
            active_only: true,
            ordering: '-license_date'
        });
    };

    return (
        <div className="container-fluid" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '24px' }}>
            {/* Professional Header */}
            <div className="row mb-4">
                <div className="col-12">
                    <div style={{
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        padding: '32px',
                        borderRadius: '12px',
                        boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                        color: 'white'
                    }}>
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '8px' }}>
                            <i className="bi bi-journal-text me-3"></i>
                            License Ledger
                        </h1>
                        <p style={{ fontSize: '1.05rem', marginBottom: '0', opacity: '0.95' }}>
                            Track and manage available balance for DFIA and Incentive licenses
                        </p>
                    </div>
                </div>
            </div>

            {/* Summary Cards - Business Grade */}
            {summary && (
                <div className="row mb-4">
                    <div className="col-lg-6 mb-3 mb-lg-0">
                        <div className="card border-0 shadow-sm h-100" style={{ borderLeft: '4px solid #4285f4' }}>
                            <div className="card-body p-4">
                                <div className="d-flex align-items-center mb-3">
                                    <div style={{
                                        width: '48px',
                                        height: '48px',
                                        borderRadius: '12px',
                                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        marginRight: '16px'
                                    }}>
                                        <i className="bi bi-globe text-white" style={{ fontSize: '24px' }}></i>
                                    </div>
                                    <div>
                                        <h5 className="mb-0" style={{ fontSize: '1.25rem', fontWeight: '700', color: '#2c3e50' }}>
                                            DFIA Licenses
                                        </h5>
                                        <p className="text-muted mb-0" style={{ fontSize: '0.9rem' }}>
                                            {summary.dfia.total_licenses} Active Licenses
                                        </p>
                                    </div>
                                </div>

                                <div className="row g-3 mb-3">
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Total Value
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#4285f4' }}>
                                                $ {formatIndianNumber(summary.dfia.total_value_usd, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#e8f5e9', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Available Balance
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2e7d32' }}>
                                                $ {formatIndianNumber(summary.dfia.balance_value_usd, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                </div>

                                <hr style={{ margin: '20px 0', borderColor: '#dee2e6' }} />

                                <div className="row g-3">
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Sold Value</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#d32f2f' }}>
                                            $ {formatIndianNumber(summary.dfia.sold_value_usd, 2)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Purchase (₹)</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#f57c00' }}>
                                            ₹ {formatIndianNumber(summary.dfia.purchase_amount_inr, 0)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Profit/Loss</p>
                                        <p className="mb-0" style={{
                                            fontSize: '1.1rem',
                                            fontWeight: '700',
                                            color: summary.dfia.profit_loss_inr >= 0 ? '#2e7d32' : '#d32f2f'
                                        }}>
                                            {summary.dfia.profit_loss_inr >= 0 ? '+' : ''}₹ {formatIndianNumber(Math.abs(summary.dfia.profit_loss_inr), 2)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="col-lg-6">
                        <div className="card border-0 shadow-sm h-100" style={{ borderLeft: '4px solid #00acc1' }}>
                            <div className="card-body p-4">
                                <div className="d-flex align-items-center mb-3">
                                    <div style={{
                                        width: '48px',
                                        height: '48px',
                                        borderRadius: '12px',
                                        background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        marginRight: '16px'
                                    }}>
                                        <i className="bi bi-trophy text-white" style={{ fontSize: '24px' }}></i>
                                    </div>
                                    <div>
                                        <h5 className="mb-0" style={{ fontSize: '1.25rem', fontWeight: '700', color: '#2c3e50' }}>
                                            Incentive Licenses
                                        </h5>
                                        <p className="text-muted mb-0" style={{ fontSize: '0.9rem' }}>
                                            {summary.incentive.total_licenses} Active Licenses
                                        </p>
                                    </div>
                                </div>

                                <div className="row g-3 mb-3">
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#f8f9fa', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Total Value
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#00acc1' }}>
                                                ₹ {formatIndianNumber(summary.incentive.total_value_inr, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                    <div className="col-6">
                                        <div style={{ padding: '16px', background: '#e8f5e9', borderRadius: '8px' }}>
                                            <p className="text-muted mb-1" style={{ fontSize: '0.85rem', fontWeight: '500' }}>
                                                Available Balance
                                            </p>
                                            <h4 className="mb-0" style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2e7d32' }}>
                                                ₹ {formatIndianNumber(summary.incentive.balance_value_inr, 2)}
                                            </h4>
                                        </div>
                                    </div>
                                </div>

                                <hr style={{ margin: '20px 0', borderColor: '#dee2e6' }} />

                                <div className="row g-3">
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Sold Value</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#d32f2f' }}>
                                            ₹ {formatIndianNumber(summary.incentive.sold_value_inr, 2)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Purchase (₹)</p>
                                        <p className="mb-0" style={{ fontSize: '1.1rem', fontWeight: '600', color: '#f57c00' }}>
                                            ₹ {formatIndianNumber(summary.incentive.purchase_amount_inr, 0)}
                                        </p>
                                    </div>
                                    <div className="col-4">
                                        <p className="text-muted mb-1" style={{ fontSize: '0.8rem' }}>Profit/Loss</p>
                                        <p className="mb-0" style={{
                                            fontSize: '1.1rem',
                                            fontWeight: '700',
                                            color: summary.incentive.profit_loss_inr >= 0 ? '#2e7d32' : '#d32f2f'
                                        }}>
                                            {summary.incentive.profit_loss_inr >= 0 ? '+' : ''}₹ {formatIndianNumber(Math.abs(summary.incentive.profit_loss_inr), 2)}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Enhanced Filters Section */}
            <div className="card border-0 shadow-sm mb-4">
                <div className="card-body p-4">
                    <div className="d-flex align-items-center mb-3">
                        <i className="bi bi-funnel text-primary me-2" style={{ fontSize: '1.25rem' }}></i>
                        <h5 className="mb-0" style={{ fontWeight: '600', color: '#2c3e50' }}>Filters & Search</h5>
                    </div>
                    <div className="row g-3">
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                License Type
                            </label>
                            <select
                                className="form-select"
                                value={filters.license_type}
                                onChange={(e) => handleFilterChange('license_type', e.target.value)}
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
                            >
                                {licenseTypeOptions.map(opt => (
                                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                                ))}
                            </select>
                        </div>
                        <div className="col-lg-2 col-md-3">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                Min Balance
                            </label>
                            <input
                                type="number"
                                className="form-control"
                                value={filters.min_balance}
                                onChange={(e) => handleFilterChange('min_balance', e.target.value)}
                                placeholder="0"
                                step="100"
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-3 col-md-5">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                Search
                            </label>
                            <div className="input-group">
                                <span className="input-group-text bg-white" style={{ borderRight: 'none' }}>
                                    <i className="bi bi-search text-muted"></i>
                                </span>
                                <input
                                    type="text"
                                    className="form-control"
                                    value={filters.search}
                                    onChange={(e) => handleFilterChange('search', e.target.value)}
                                    placeholder="License # or exporter..."
                                    style={{ borderLeft: 'none', fontSize: '0.95rem' }}
                                />
                            </div>
                        </div>
                        <div className="col-lg-2 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                Sort By
                            </label>
                            <select
                                className="form-select"
                                value={filters.ordering}
                                onChange={(e) => handleFilterChange('ordering', e.target.value)}
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
                            >
                                <option value="-license_date">Latest First</option>
                                <option value="license_date">Oldest First</option>
                                <option value="-balance_value">Highest Balance</option>
                                <option value="balance_value">Lowest Balance</option>
                            </select>
                        </div>
                        <div className="col-lg-2 col-md-4 d-flex align-items-end">
                            <div className="form-check form-switch">
                                <input
                                    type="checkbox"
                                    className="form-check-input"
                                    id="activeOnly"
                                    checked={filters.active_only}
                                    onChange={(e) => handleFilterChange('active_only', e.target.checked)}
                                    style={{ cursor: 'pointer' }}
                                />
                                <label className="form-check-label" htmlFor="activeOnly" style={{ fontSize: '0.9rem', fontWeight: '500', cursor: 'pointer' }}>
                                    Active Only
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Purchase Date Filter Row */}
                    <div className="row g-3 mt-2">
                        <div className="col-12">
                            <div className="d-flex align-items-center mb-2">
                                <i className="bi bi-calendar-range text-primary me-2"></i>
                                <strong style={{ fontSize: '0.9rem', color: '#5a6c7d' }}>Purchase Date Range</strong>
                                <small className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>(Filter licenses by purchase date)</small>
                            </div>
                        </div>
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                <i className="bi bi-calendar-check me-1"></i>From Date
                            </label>
                            <input
                                type="date"
                                className="form-control"
                                value={filters.purchase_date_from}
                                onChange={(e) => handleFilterChange('purchase_date_from', e.target.value)}
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.9rem', fontWeight: '600', color: '#5a6c7d' }}>
                                <i className="bi bi-calendar-x me-1"></i>To Date
                            </label>
                            <input
                                type="date"
                                className="form-control"
                                value={filters.purchase_date_to}
                                onChange={(e) => handleFilterChange('purchase_date_to', e.target.value)}
                                style={{ borderColor: '#ced4da', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-2 col-md-4 d-flex align-items-end">
                            <button
                                className="btn btn-sm btn-outline-secondary w-100"
                                onClick={() => {
                                    handleFilterChange('purchase_date_from', '');
                                    handleFilterChange('purchase_date_to', '');
                                }}
                                disabled={!filters.purchase_date_from && !filters.purchase_date_to}
                                style={{ fontWeight: '500' }}
                            >
                                <i className="bi bi-x-circle me-1"></i>Clear Dates
                            </button>
                        </div>
                    </div>
                </div>
            </div>

            {/* Enhanced License Table */}
            <div className="card border-0 shadow-sm">
                <div className="card-header bg-white border-0 pt-4 px-4 pb-0">
                    <div className="d-flex justify-content-between align-items-center mb-3">
                        <h5 className="mb-0" style={{ fontWeight: '600', color: '#2c3e50' }}>
                            <i className="bi bi-table text-primary me-2"></i>
                            License Listings
                        </h5>
                        <div className="d-flex align-items-center gap-2">
                            <span className="badge bg-light text-dark" style={{ fontSize: '0.9rem', fontWeight: '500' }}>
                                {licenses.length} {licenses.length === 1 ? 'License' : 'Licenses'}
                            </span>
                            <div className="btn-group" role="group">
                                <button
                                    className="btn btn-sm btn-outline-primary"
                                    onClick={handleExportWithFilters}
                                    disabled={loading || exportingPdf}
                                    title="Export with current filters"
                                    style={{ fontWeight: '600' }}
                                >
                                    {exportingPdf ? (
                                        <>
                                            <span className="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>
                                            Exporting...
                                        </>
                                    ) : (
                                        <>
                                            <i className="bi bi-file-earmark-pdf me-1"></i>
                                            Export All PDF
                                        </>
                                    )}
                                </button>
                                <button
                                    type="button"
                                    className="btn btn-sm btn-outline-primary dropdown-toggle dropdown-toggle-split"
                                    data-bs-toggle="dropdown"
                                    aria-expanded="false"
                                    disabled={loading || exportingPdf}
                                    style={{ fontWeight: '600' }}
                                >
                                    <span className="visually-hidden">Toggle Dropdown</span>
                                </button>
                                <ul className="dropdown-menu dropdown-menu-end" style={{ minWidth: '250px' }}>
                                    <li><h6 className="dropdown-header" style={{ fontSize: '0.75rem', color: '#6c757d', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Quick Export Options</h6></li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportWithFilters} disabled={exportingPdf}>
                                            <i className="bi bi-funnel-fill me-2 text-primary"></i>
                                            <strong>Current Filters</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Export with applied filters
                                            </small>
                                        </button>
                                    </li>
                                    <li><hr className="dropdown-divider" /></li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportAllActive} disabled={exportingPdf}>
                                            <i className="bi bi-check-circle me-2 text-success"></i>
                                            <strong>All Active Licenses</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                All types, active only
                                            </small>
                                        </button>
                                    </li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportAllIncludingExpired} disabled={exportingPdf}>
                                            <i className="bi bi-list-ul me-2 text-secondary"></i>
                                            <strong>All Licenses (Inc. Expired)</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Complete list with expired
                                            </small>
                                        </button>
                                    </li>
                                    <li><hr className="dropdown-divider" /></li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportDFIAOnly} disabled={exportingPdf}>
                                            <i className="bi bi-globe me-2 text-info"></i>
                                            <strong>DFIA Only</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Active DFIA licenses
                                            </small>
                                        </button>
                                    </li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportIncentiveOnly} disabled={exportingPdf}>
                                            <i className="bi bi-trophy me-2 text-warning"></i>
                                            <strong>Incentive Only</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                All incentive schemes
                                            </small>
                                        </button>
                                    </li>
                                    <li><hr className="dropdown-divider" /></li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportWithBalance} disabled={exportingPdf}>
                                            <i className="bi bi-cash-stack me-2 text-success"></i>
                                            <strong>With Balance (≥100)</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Sorted by highest balance
                                            </small>
                                        </button>
                                    </li>
                                    <li><hr className="dropdown-divider" /></li>
                                    <li><h6 className="dropdown-header" style={{ fontSize: '0.75rem', color: '#6c757d', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Purchase Date Ranges</h6></li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportThisMonth} disabled={exportingPdf}>
                                            <i className="bi bi-calendar-month me-2 text-primary"></i>
                                            <strong>This Month</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Purchased in current month
                                            </small>
                                        </button>
                                    </li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportLastMonth} disabled={exportingPdf}>
                                            <i className="bi bi-calendar3 me-2 text-info"></i>
                                            <strong>Last Month</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Purchased in previous month
                                            </small>
                                        </button>
                                    </li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportLast3Months} disabled={exportingPdf}>
                                            <i className="bi bi-calendar-range me-2 text-warning"></i>
                                            <strong>Last 3 Months</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Purchased in last quarter
                                            </small>
                                        </button>
                                    </li>
                                    <li>
                                        <button className="dropdown-item" onClick={handleExportThisYear} disabled={exportingPdf}>
                                            <i className="bi bi-calendar-year me-2 text-success"></i>
                                            <strong>This Year</strong>
                                            <small className="d-block text-muted" style={{ fontSize: '0.75rem', marginLeft: '24px' }}>
                                                Purchased in current year
                                            </small>
                                        </button>
                                    </li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
                <div className="card-body p-0">
                    <div style={{ overflowX: 'auto' }}>
                        <table className="table table-hover mb-0" style={{ minWidth: '1200px' }}>
                            <thead style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                                <tr>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Type
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        License #
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Issue Date
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Expiry
                                    </th>
                                    <th style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Exporter
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Total Value
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Balance
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Purchase (₹)
                                    </th>
                                    <th className="text-end" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        P/L (₹)
                                    </th>
                                    <th className="text-center" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Status
                                    </th>
                                    <th className="text-center" style={{ padding: '16px', fontSize: '0.85rem', fontWeight: '700', color: '#495057', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Actions
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {loading ? (
                                    <tr>
                                        <td colSpan="11" className="text-center py-5">
                                            <div className="spinner-border text-primary" role="status" style={{ width: '3rem', height: '3rem' }}>
                                                <span className="visually-hidden">Loading...</span>
                                            </div>
                                            <p className="text-muted mt-3 mb-0">Loading license data...</p>
                                        </td>
                                    </tr>
                                ) : licenses.length === 0 ? (
                                    <tr>
                                        <td colSpan="11" className="text-center py-5">
                                            <i className="bi bi-inbox text-muted" style={{ fontSize: '3rem' }}></i>
                                            <p className="text-muted mt-3 mb-0" style={{ fontSize: '1.05rem' }}>
                                                No licenses found matching your criteria
                                            </p>
                                        </td>
                                    </tr>
                                ) : (
                                    licenses.map((license) => (
                                        <tr key={`${license.license_type}-${license.id}`}
                                            style={{
                                                borderBottom: '1px solid #f0f0f0',
                                                transition: 'all 0.2s ease'
                                            }}
                                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#f8f9fa'}
                                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                        >
                                            <td style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span className={`badge ${license.license_type === 'DFIA' ? 'bg-primary' : 'bg-info'}`}
                                                    style={{ fontSize: '0.8rem', fontWeight: '600', padding: '6px 12px', borderRadius: '6px' }}>
                                                    {license.license_type}
                                                </span>
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span style={{ fontSize: '0.95rem', fontWeight: '600', color: '#2c3e50' }}>
                                                    {license.license_number}
                                                </span>
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem', color: '#5a6c7d' }}>
                                                {formatDate(license.license_date)}
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem' }}>
                                                <span style={{ color: license.is_expired ? '#d32f2f' : '#5a6c7d' }}>
                                                    {formatDate(license.license_expiry_date)}
                                                </span>
                                                {license.is_expired && (
                                                    <span className="badge bg-danger ms-2" style={{ fontSize: '0.7rem', padding: '3px 6px' }}>
                                                        EXPIRED
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem', color: '#5a6c7d', maxWidth: '200px' }}>
                                                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                                    title={license.exporter_name}>
                                                    {license.exporter_name}
                                                </div>
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.95rem', fontWeight: '600', color: '#2c3e50' }}>
                                                {formatCurrency(license.total_value, license.currency)}
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span style={{
                                                    fontSize: '1rem',
                                                    fontWeight: '700',
                                                    color: license.balance_value > 0 ? '#2e7d32' : '#9e9e9e'
                                                }}>
                                                    {formatCurrency(license.balance_value, license.currency)}
                                                </span>
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle', fontSize: '0.9rem', color: '#f57c00', fontWeight: '600' }}>
                                                ₹ {formatIndianNumber(license.purchase_amount || 0, 0)}
                                            </td>
                                            <td className="text-end" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <span style={{
                                                    fontSize: '0.95rem',
                                                    fontWeight: '700',
                                                    color: (license.profit_loss || 0) >= 0 ? '#2e7d32' : '#d32f2f'
                                                }}>
                                                    {(license.profit_loss || 0) >= 0 ? '+' : ''}₹ {formatIndianNumber(Math.abs(license.profit_loss || 0), 0)}
                                                </span>
                                            </td>
                                            <td className="text-center" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                {getSoldStatusBadge(license.sold_status)}
                                            </td>
                                            <td className="text-center" style={{ padding: '16px', verticalAlign: 'middle' }}>
                                                <button
                                                    className="btn btn-sm me-2"
                                                    onClick={() => handleViewDetails(license)}
                                                    title="View Ledger Details"
                                                    style={{
                                                        backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                                        border: '1px solid rgba(102, 126, 234, 0.3)',
                                                        color: '#667eea',
                                                        padding: '6px 12px',
                                                        borderRadius: '6px',
                                                        fontSize: '0.85rem',
                                                        fontWeight: '500'
                                                    }}
                                                >
                                                    <i className="bi bi-journal-text me-1"></i>
                                                    View
                                                </button>
                                                {license.balance_value > 0 && (
                                                    <button
                                                        className="btn btn-sm btn-success"
                                                        onClick={() => handleCreateTrade(license)}
                                                        title="Create Sale"
                                                        style={{
                                                            padding: '6px 12px',
                                                            borderRadius: '6px',
                                                            fontSize: '0.85rem',
                                                            fontWeight: '500'
                                                        }}
                                                    >
                                                        <i className="bi bi-cart-plus me-1"></i>
                                                        Trade
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );
}
