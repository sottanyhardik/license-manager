import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'react-toastify';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { formatDate } from '../utils/dateFormatter';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import AsyncSelectField from '../components/AsyncSelectField';

export default function LicenseLedger() {
    const navigate = useNavigate();
    const [licenses, setLicenses] = useState([]);
    const [summary, setSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [exportingPdf, setExportingPdf] = useState(false);

    // Get current financial year dates (April 1 to March 31)
    const getCurrentFinancialYear = () => {
        const today = new Date();
        const currentYear = today.getFullYear();
        const currentMonth = today.getMonth(); // 0-11

        // If current month is Jan-Mar (0-2), FY started last year
        // If current month is Apr-Dec (3-11), FY started this year
        const fyStartYear = currentMonth <= 2 ? currentYear - 1 : currentYear;

        const fyStart = `${fyStartYear}-04-01`;
        const fyEnd = `${fyStartYear + 1}-03-31`;

        return { fyStart, fyEnd };
    };

    const getPreviousFinancialYear = () => {
        const today = new Date();
        const currentYear = today.getFullYear();
        const currentMonth = today.getMonth();

        const fyStartYear = currentMonth <= 2 ? currentYear - 2 : currentYear - 1;

        const fyStart = `${fyStartYear}-04-01`;
        const fyEnd = `${fyStartYear + 1}-03-31`;

        return { fyStart, fyEnd };
    };

    const { fyStart: currentFYStart, fyEnd: currentFYEnd } = getCurrentFinancialYear();

    const [filters, setFilters] = useState({
        license_type: 'ALL',
        min_balance: '',
        search: '',
        company: null,
        active_only: true,
        ordering: '-license_date',
        purchase_date_from: currentFYStart,  // Default to current FY start
        purchase_date_to: currentFYEnd       // Default to current FY end
    });

    const licenseTypeOptions = [
        { value: 'ALL', label: 'All Licenses', icon: 'bi-list-ul' },
        { value: 'DFIA', label: 'DFIA Only', icon: 'bi-globe' },
        { value: 'INCENTIVE', label: 'All Incentive', icon: 'bi-trophy' },
        { value: 'RODTEP', label: 'RODTEP', icon: 'bi-award' },
        { value: 'ROSTL', label: 'ROSTL', icon: 'bi-badge-tm' },
        { value: 'MEIS', label: 'MEIS', icon: 'bi-star' },
    ];

    // Centralized function to build filter params
    const buildFilterParams = useCallback((additionalFilters = {}) => {
        const params = new URLSearchParams();

        const currentFilters = { ...filters, ...additionalFilters };

        if (currentFilters.license_type) params.append('license_type', currentFilters.license_type);
        if (currentFilters.min_balance) params.append('min_balance', currentFilters.min_balance);
        if (currentFilters.search) params.append('search', currentFilters.search);
        if (currentFilters.company) params.append('company', currentFilters.company.value || currentFilters.company);
        if (currentFilters.ordering) params.append('ordering', currentFilters.ordering);
        if (currentFilters.purchase_date_from) params.append('purchase_date_from', currentFilters.purchase_date_from);
        if (currentFilters.purchase_date_to) params.append('purchase_date_to', currentFilters.purchase_date_to);
        params.append('active_only', currentFilters.active_only);

        // Include no_purchases parameter if provided
        if (currentFilters.no_purchases) params.append('no_purchases', currentFilters.no_purchases);

        return params;
    }, [filters]);

    useEffect(() => {
        // Only fetch data if company is selected
        if (filters.company) {
            fetchLedgerData();
            fetchSummary();
        } else {
            // Clear data when no company selected
            setLicenses([]);
            setSummary(null);
            setLoading(false);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        filters.license_type,
        filters.min_balance,
        filters.search,
        filters.company,
        filters.active_only,
        filters.ordering,
        filters.purchase_date_from,
        filters.purchase_date_to
    ]);

    const fetchLedgerData = async () => {
        // Don't fetch if no company selected
        if (!filters.company) {
            setLicenses([]);
            setLoading(false);
            return;
        }

        setLoading(true);
        try {
            const params = buildFilterParams();
            const response = await api.get(`license-ledger/?${params.toString()}`);

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
            toast.error(error?.response?.data?.error || 'Failed to load ledger data.');
            setLicenses([]);
        } finally {
            setLoading(false);
        }
    };

    const fetchSummary = async () => {
        // Don't fetch if no company selected
        if (!filters.company) {
            setSummary(null);
            return;
        }

        try {
            const params = buildFilterParams();
            const response = await api.get(`license-ledger/summary/?${params.toString()}`);
            setSummary(response.data);
        } catch (error) {
            toast.error('Failed to load summary data.');
        }
    };

    const handleFilterChange = (field, value) => {
        setFilters(prev => ({ ...prev, [field]: value }));
    };

    const setCurrentFinancialYear = () => {
        const { fyStart, fyEnd } = getCurrentFinancialYear();
        setFilters(prev => ({
            ...prev,
            purchase_date_from: fyStart,
            purchase_date_to: fyEnd
        }));
    };

    const setPreviousFinancialYear = () => {
        const { fyStart, fyEnd } = getPreviousFinancialYear();
        setFilters(prev => ({
            ...prev,
            purchase_date_from: fyStart,
            purchase_date_to: fyEnd
        }));
    };

    const clearDateFilter = () => {
        setFilters(prev => ({
            ...prev,
            purchase_date_from: '',
            purchase_date_to: ''
        }));
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
        const companyId = filters.company?.value || filters.company;
        const path = companyId
            ? `/license-ledger/${license.id}/${companyId}`
            : `/license-ledger/${license.id}`;
        navigate(path, {
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

    const handleExportPdf = useCallback(async () => {
        if (!filters.company) {
            toast.error('Please select a company first');
            return;
        }

        try {
            setExportingPdf(true);

            const params = buildFilterParams();
            params.set('detailed', 'true');  // Request detailed transaction view
            const pdfViewerUrl = `/pdf-viewer?url=${encodeURIComponent(`/license-ledger/export/all/?${params.toString()}`)}`;
            const newWindow = window.open(pdfViewerUrl, '_blank');

            if (newWindow) {
                toast.success('PDF opened in new tab - you can refresh to regenerate');
            } else {
                toast.error('Popup blocked. Please allow popups for this site.');
            }
        } catch (error) {
            console.error('Error opening PDF:', error);
            toast.error('Failed to open PDF viewer.');
        } finally {
            setExportingPdf(false);
        }
    }, [filters.company, buildFilterParams]);

    const handleExportNoPurchases = useCallback(async () => {
        try {
            setExportingPdf(true);

            // Only use no_purchases parameter, ignore all other filters
            const params = new URLSearchParams();
            params.append('no_purchases', 'true');

            const pdfViewerUrl = `/pdf-viewer?url=${encodeURIComponent(`/license-ledger/export/all/?${params.toString()}`)}`;
            const newWindow = window.open(pdfViewerUrl, '_blank');

            if (newWindow) {
                toast.success('PDF with licenses without purchases opened');
            } else {
                toast.error('Popup blocked. Please allow popups for this site.');
            }
        } catch (error) {
            console.error('Error opening PDF:', error);
            toast.error('Failed to open PDF viewer.');
        } finally {
            setExportingPdf(false);
        }
    }, []);

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
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
                        <i className="bi bi-journal-text me-2" style={{ color: '#4F46E5' }}></i>
                        License Ledger
                    </h4>
                    <small className="text-muted">Track available balance for DFIA and Incentive licenses</small>
                </div>
                <div className="d-flex gap-2">
                    {filters.company && (
                        <button
                            className="btn btn-sm btn-outline-primary"
                            onClick={handleExportPdf}
                            disabled={exportingPdf}
                        >
                            <i className="bi bi-file-earmark-pdf me-1"></i>Export PDF
                        </button>
                    )}
                    <button
                        className="btn btn-sm btn-outline-secondary"
                        onClick={handleExportNoPurchases}
                        disabled={exportingPdf}
                    >
                        <i className="bi bi-file-earmark-excel me-1"></i>No Purchases
                    </button>
                </div>
            </div>

            {/* Summary Cards */}
            {summary && (
                <div className="row g-3 mb-4">
                    <div className="col-lg-6">
                        <div className="card border-0 shadow-sm" style={{ borderLeft: '3px solid #4F46E5' }}>
                            <div className="card-header bg-white border-bottom py-2 px-3 d-flex align-items-center gap-2">
                                <i className="bi bi-globe" style={{ color: '#4F46E5', fontSize: '0.95rem' }}></i>
                                <span className="fw-semibold small">DFIA Licenses</span>
                                <span className="badge ms-auto" style={{ background: '#4F46E5', fontSize: '0.7rem' }}>{summary.dfia.total_licenses} active</span>
                            </div>
                            <div className="card-body py-2 px-3">
                                <div className="row g-0 text-center">
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Total Value</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#4F46E5' }}>$ {formatIndianNumber(summary.dfia.total_value_usd, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Balance</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#10b981' }}>$ {formatIndianNumber(summary.dfia.balance_value_usd, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Purchase</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#f59e0b' }}>₹{formatIndianNumber(summary.dfia.purchase_amount_inr, 0)}</div>
                                    </div>
                                    <div className="col-3 py-2">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>P / L</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: summary.dfia.profit_loss_inr >= 0 ? '#10b981' : '#ef4444' }}>
                                            {summary.dfia.profit_loss_inr >= 0 ? '+' : ''}₹{formatIndianNumber(Math.abs(summary.dfia.profit_loss_inr), 0)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div className="col-lg-6">
                        <div className="card border-0 shadow-sm" style={{ borderLeft: '3px solid #06b6d4' }}>
                            <div className="card-header bg-white border-bottom py-2 px-3 d-flex align-items-center gap-2">
                                <i className="bi bi-trophy" style={{ color: '#06b6d4', fontSize: '0.95rem' }}></i>
                                <span className="fw-semibold small">Incentive Licenses</span>
                                <span className="badge ms-auto" style={{ background: '#06b6d4', fontSize: '0.7rem' }}>{summary.incentive.total_licenses} active</span>
                            </div>
                            <div className="card-body py-2 px-3">
                                <div className="row g-0 text-center">
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Total Value</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#4F46E5' }}>₹{formatIndianNumber(summary.incentive.total_value_inr, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Balance</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#10b981' }}>₹{formatIndianNumber(summary.incentive.balance_value_inr, 2)}</div>
                                    </div>
                                    <div className="col-3 py-2 border-end">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>Purchase</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: '#f59e0b' }}>₹{formatIndianNumber(summary.incentive.purchase_amount_inr, 0)}</div>
                                    </div>
                                    <div className="col-3 py-2">
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px' }}>P / L</div>
                                        <div style={{ fontSize: '0.88rem', fontWeight: '700', color: summary.incentive.profit_loss_inr >= 0 ? '#10b981' : '#ef4444' }}>
                                            {summary.incentive.profit_loss_inr >= 0 ? '+' : ''}₹{formatIndianNumber(Math.abs(summary.incentive.profit_loss_inr), 0)}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* Filters Section */}
            <div className="card border-0 shadow-sm mb-4">
                <div className="card-header bg-white border-bottom py-2 px-3 d-flex align-items-center justify-content-between">
                    <div className="d-flex align-items-center gap-2">
                        <i className="bi bi-funnel" style={{ color: '#4F46E5' }}></i>
                        <h6 className="mb-0 fw-semibold">Filters & Search</h6>
                        {filters.company && (
                            <span className="badge bg-info ms-1" style={{ fontSize: '0.7rem' }}>
                                <i className="bi bi-building me-1"></i>{filters.company.label}
                            </span>
                        )}
                    </div>
                    {filters.company && (
                        <button className="btn btn-sm btn-outline-secondary" onClick={() => handleFilterChange('company', null)}>
                            <i className="bi bi-x-circle me-1"></i>Clear Company
                        </button>
                    )}
                </div>
                <div className="card-body p-3">
                    <div className="row g-3">
                        <div className="col-lg-3 col-md-5">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                <i className="bi bi-building me-1"></i>
                                Company Filter
                            </label>
                            <AsyncSelectField
                                endpoint="masters/companies/"
                                labelField="name"
                                valueField="id"
                                value={filters.company}
                                onChange={(value) => handleFilterChange('company', value)}
                                isMulti={false}
                                placeholder="Select company to view their ledger..."
                                loadOnMount={false}
                            />
                            <small className="text-muted">Filter by trades with specific company</small>
                        </div>
                        <div className="col-lg-3 col-md-6">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                License Type
                            </label>
                            <div className="d-flex flex-wrap gap-1">
                                {licenseTypeOptions.map(opt => (
                                    <button
                                        key={opt.value}
                                        type="button"
                                        onClick={() => handleFilterChange('license_type', opt.value)}
                                        style={{
                                            fontSize: '0.75rem', fontWeight: '600', padding: '4px 10px', borderRadius: '20px',
                                            background: filters.license_type === opt.value ? '#4F46E5' : 'white',
                                            color: filters.license_type === opt.value ? 'white' : 'var(--text-secondary)',
                                            border: `1px solid ${filters.license_type === opt.value ? '#4F46E5' : '#d1d5db'}`,
                                            cursor: 'pointer', transition: 'all 0.15s',
                                        }}
                                    >
                                        {opt.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div className="col-lg-2 col-md-3">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                Min Balance
                            </label>
                            <input
                                type="number"
                                className="form-control"
                                value={filters.min_balance}
                                onChange={(e) => handleFilterChange('min_balance', e.target.value)}
                                placeholder="0"
                                step="100"
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-3 col-md-5">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
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
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                Sort By
                            </label>
                            <select
                                className="form-select"
                                value={filters.ordering}
                                onChange={(e) => handleFilterChange('ordering', e.target.value)}
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
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
                                <label className="form-check-label" htmlFor="activeOnly" style={{ fontSize: '0.78rem', fontWeight: '600', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                                    Active Only
                                </label>
                            </div>
                        </div>
                    </div>

                    {/* Purchase Date Filter Row */}
                    <div className="row g-3 mt-2">
                        <div className="col-12">
                            <div className="d-flex align-items-center justify-content-between mb-2">
                                <div className="d-flex align-items-center">
                                    <i className="bi bi-calendar-range text-primary me-2"></i>
                                    <strong style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>Purchase Date Range</strong>
                                    <small className="text-muted ms-2" style={{ fontSize: '0.8rem' }}>(Defaults to current FY: Apr-Mar)</small>
                                </div>
                                <div className="btn-group" role="group">
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-primary"
                                        onClick={setCurrentFinancialYear}
                                        style={{ fontSize: '0.75rem' }}
                                    >
                                        <i className="bi bi-calendar-check me-1"></i>Current FY
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-secondary"
                                        onClick={setPreviousFinancialYear}
                                        style={{ fontSize: '0.75rem' }}
                                    >
                                        <i className="bi bi-calendar3 me-1"></i>Previous FY
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-danger"
                                        onClick={clearDateFilter}
                                        disabled={!filters.purchase_date_from && !filters.purchase_date_to}
                                        style={{ fontSize: '0.75rem' }}
                                    >
                                        <i className="bi bi-x-circle me-1"></i>Clear
                                    </button>
                                </div>
                            </div>
                        </div>
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                <i className="bi bi-calendar-check me-1"></i>From Date
                            </label>
                            <input
                                type="date"
                                className="form-control"
                                value={filters.purchase_date_from}
                                onChange={(e) => handleFilterChange('purchase_date_from', e.target.value)}
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
                            />
                        </div>
                        <div className="col-lg-3 col-md-4">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                                <i className="bi bi-calendar-x me-1"></i>To Date
                            </label>
                            <input
                                type="date"
                                className="form-control"
                                value={filters.purchase_date_to}
                                onChange={(e) => handleFilterChange('purchase_date_to', e.target.value)}
                                style={{ borderColor: 'var(--bs-gray-300)', fontSize: '0.95rem' }}
                            />
                        </div>
                    </div>
                </div>
            </div>

            {/* License Table */}
            <div className="card border-0 shadow-sm">
                <div className="card-header bg-white border-bottom py-2 px-3 d-flex align-items-center justify-content-between">
                    <div className="d-flex align-items-center gap-2">
                        <i className="bi bi-table" style={{ color: '#4F46E5' }}></i>
                        <h6 className="mb-0 fw-semibold">License Listings</h6>
                    </div>
                    <span className="badge" style={{ background: '#e0e7ff', color: '#4F46E5', fontSize: '0.78rem', fontWeight: '600' }}>
                        {licenses.length} {licenses.length === 1 ? 'License' : 'Licenses'}
                    </span>
                </div>
                <div className="card-body p-0">
                    <div style={{ overflowX: 'auto' }}>
                        <table className="table table-hover mb-0" style={{ minWidth: '1200px' }}>
                            <thead style={{ backgroundColor: 'var(--bs-gray-50)', borderBottom: '2px solid #dee2e6' }}>
                                <tr>
                                    <th style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Type
                                    </th>
                                    <th style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        License #
                                    </th>
                                    <th style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Issue Date
                                    </th>
                                    <th style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Expiry
                                    </th>
                                    <th style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Exporter
                                    </th>
                                    <th className="text-end" style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Total Value
                                    </th>
                                    <th className="text-end" style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Balance
                                    </th>
                                    <th className="text-end" style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Purchase (₹)
                                    </th>
                                    <th className="text-end" style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        P/L (₹)
                                    </th>
                                    <th className="text-center" style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Status
                                    </th>
                                    <th className="text-center" style={{ padding: '9px 12px', fontSize: '0.75rem', fontWeight: '700', color: 'var(--bs-gray-500)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        Actions
                                    </th>
                                </tr>
                            </thead>
                            <tbody>
                                {!filters.company ? (
                                    <tr>
                                        <td colSpan="11" className="text-center py-5">
                                            <i className="bi bi-building" style={{ fontSize: '2.5rem', color: 'var(--bs-gray-300)' }}></i>
                                            <p className="mt-3 mb-1 fw-semibold" style={{ color: 'var(--text-dark)', fontSize: '0.95rem' }}>Select a Company</p>
                                            <p className="text-muted mb-0 small">
                                                Choose a company from the filter above to view their license ledger
                                            </p>
                                        </td>
                                    </tr>
                                ) : loading ? (
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
                                                No licenses found for {filters.company.label}
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
                                            onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--bs-gray-50)'}
                                            onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                                        >
                                            <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                                                <span className={`badge ${license.license_type === 'DFIA' ? 'bg-primary' : 'bg-info'}`}
                                                    style={{ fontSize: '0.8rem', fontWeight: '600', padding: '6px 12px', borderRadius: '6px' }}>
                                                    {license.license_type}
                                                </span>
                                            </td>
                                            <td style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                                                <span style={{ fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-dark)' }}>
                                                    {license.license_number}
                                                </span>
                                            </td>
                                            <td style={{ padding: '10px 12px', verticalAlign: 'middle', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                                                {formatDate(license.license_date)}
                                            </td>
                                            <td style={{ padding: '10px 12px', verticalAlign: 'middle', fontSize: '0.9rem' }}>
                                                <span style={{ color: license.is_expired ? 'var(--danger-color)' : 'var(--text-secondary)' }}>
                                                    {formatDate(license.license_expiry_date)}
                                                </span>
                                                {license.is_expired && (
                                                    <span className="badge bg-danger ms-2" style={{ fontSize: '0.7rem', padding: '3px 6px' }}>
                                                        EXPIRED
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{ padding: '10px 12px', verticalAlign: 'middle', fontSize: '0.82rem', color: 'var(--text-secondary)', maxWidth: '200px' }}>
                                                <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                                                    title={license.exporter_name}>
                                                    {license.exporter_name}
                                                </div>
                                            </td>
                                            <td className="text-end" style={{ padding: '10px 12px', verticalAlign: 'middle', fontSize: '0.85rem', fontWeight: '600', color: 'var(--text-dark)' }}>
                                                {formatCurrency(license.total_value, license.currency)}
                                            </td>
                                            <td className="text-end" style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                                                <span style={{
                                                    fontSize: '0.88rem',
                                                    fontWeight: '700',
                                                    color: license.balance_value > 0 ? 'var(--success-text)' : 'var(--bs-gray-400)'
                                                }}>
                                                    {formatCurrency(license.balance_value, license.currency)}
                                                </span>
                                            </td>
                                            <td className="text-end" style={{ padding: '10px 12px', verticalAlign: 'middle', fontSize: '0.82rem', color: 'var(--warning-color)', fontWeight: '600' }}>
                                                ₹ {formatIndianNumber(license.purchase_amount || 0, 0)}
                                            </td>
                                            <td className="text-end" style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                                                <span style={{
                                                    fontSize: '0.82rem',
                                                    fontWeight: '700',
                                                    color: (license.profit_loss || 0) >= 0 ? 'var(--success-text)' : 'var(--danger-color)'
                                                }}>
                                                    {(license.profit_loss || 0) >= 0 ? '+' : ''}₹ {formatIndianNumber(Math.abs(license.profit_loss || 0), 0)}
                                                </span>
                                            </td>
                                            <td className="text-center" style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                                                {getSoldStatusBadge(license.sold_status)}
                                            </td>
                                            <td className="text-center" style={{ padding: '10px 12px', verticalAlign: 'middle' }}>
                                                <button
                                                    className="btn btn-sm me-2"
                                                    onClick={() => handleViewDetails(license)}
                                                    title="View Ledger Details"
                                                    style={{
                                                        backgroundColor: 'rgba(79, 70, 229, 0.08)',
                                                        border: '1px solid rgba(79, 70, 229, 0.25)',
                                                        color: '#4F46E5',
                                                        padding: '4px 10px',
                                                        borderRadius: '6px',
                                                        fontSize: '0.78rem',
                                                        fontWeight: '600'
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
                                                            padding: '4px 10px',
                                                            borderRadius: '6px',
                                                            fontSize: '0.78rem',
                                                            fontWeight: '600'
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
