import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import * as XLSX from 'xlsx';
import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';

export default function LicenseLedgerDetail() {
    const { id } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [ledger, setLedger] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Get license_type from query params or location state
    const queryParams = new URLSearchParams(location.search);
    const licenseType = queryParams.get('license_type') || location.state?.license_type || 'DFIA';

    useEffect(() => {
        fetchLedgerDetail();
    }, [id, licenseType]);

    const fetchLedgerDetail = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await api.get(`/license-ledger/${id}/ledger_detail/?license_type=${licenseType}`);
            setLedger(response.data);
        } catch (err) {
            console.error('Error fetching ledger detail:', err);
            setError(err.response?.data?.error || 'Failed to load ledger details');
        } finally {
            setLoading(false);
        }
    };

    const formatDate = (dateStr) => {
        if (!dateStr) return '-';
        return new Date(dateStr).toLocaleDateString('en-GB');
    };

    const formatCurrency = (value, currency = 'INR') => {
        if (!value && value !== 0) return '-';
        const symbol = currency === 'USD' ? '$' : '₹';
        return `${symbol}${formatIndianNumber(value, 2)}`;
    };

    if (loading) {
        return (
            <div className="container-fluid py-4">
                <div className="text-center py-5">
                    <div className="spinner-border text-primary" role="status">
                        <span className="visually-hidden">Loading...</span>
                    </div>
                </div>
            </div>
        );
    }

    if (error) {
        return (
            <div className="container-fluid py-4">
                <div className="alert alert-danger" role="alert">
                    <i className="bi bi-exclamation-triangle me-2"></i>
                    {error}
                </div>
                <button className="btn btn-primary" onClick={() => navigate(-1)}>
                    <i className="bi bi-arrow-left me-2"></i>
                    Go Back
                </button>
            </div>
        );
    }

    if (!ledger) return null;

    const isDFIA = ledger.license_type === 'DFIA';
    const hasPurchases = ledger.transactions.some(t => t.type === 'PURCHASE' || t.type === 'OPENING');
    const currentBalance = ledger.available_balance || 0;
    const isNegativeBalance = currentBalance < 0;
    const showPurchaseWarning = !hasPurchases || isNegativeBalance;

    const handleDownloadPDF = () => {
        const doc = new jsPDF('l', 'mm', 'a4'); // Landscape orientation
        const pageWidth = doc.internal.pageSize.getWidth();

        // Main Title with elegant styling
        doc.setFontSize(18);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(25, 42, 86); // Professional navy blue
        doc.text('LICENSE LEDGER STATEMENT', pageWidth / 2, 12, { align: 'center' });

        // License Type subtitle
        doc.setFontSize(10);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(41, 128, 185); // Elegant blue
        doc.text(`[ ${ledger.license_type} ]`, pageWidth / 2, 18, { align: 'center' });

        // Single elegant separator line
        doc.setDrawColor(52, 73, 94);
        doc.setLineWidth(0.5);
        doc.line(14, 22, pageWidth - 14, 22);

        // License Details - Compact layout
        doc.setFontSize(8.5);
        const leftColX = 14;
        const leftValX = 50;
        const midColX = pageWidth / 2 - 30;
        const midValX = pageWidth / 2 + 5;
        const rightColX = pageWidth - 95;
        const rightValX = pageWidth - 50;
        const rowY = 28;

        // Row 1
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(74, 85, 104);
        doc.text('License Number:', leftColX, rowY);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(0, 0, 0);
        doc.text(ledger.license_number, leftValX, rowY);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(74, 85, 104);
        doc.text('License Date:', midColX, rowY);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(0, 0, 0);
        doc.text(formatDate(ledger.license_date), midValX, rowY);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(74, 85, 104);
        doc.text('Expiry Date:', rightColX, rowY);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(0, 0, 0);
        doc.text(formatDate(ledger.expiry_date), rightValX, rowY);

        // Row 2
        const row2Y = rowY + 6;
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(74, 85, 104);
        doc.text('Exporter:', leftColX, row2Y);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(0, 0, 0);
        const exporterText = ledger.exporter || 'N/A';
        const maxExporterWidth = midColX - leftValX - 5;
        const exporterLines = doc.splitTextToSize(exporterText, maxExporterWidth);
        doc.text(exporterLines[0], leftValX, row2Y);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(74, 85, 104);
        doc.text('Total Value:', midColX, row2Y);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(0, 0, 0);
        doc.text(formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR'), midValX, row2Y);

        doc.setFont('helvetica', 'normal');
        doc.setTextColor(74, 85, 104);
        doc.text('Balance:', rightColX, row2Y);
        doc.setFont('helvetica', 'bold');
        if (currentBalance >= 0) {
            doc.setTextColor(22, 160, 133);
        } else {
            doc.setTextColor(231, 76, 60);
        }
        doc.text(formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR'), rightValX, row2Y);
        doc.setTextColor(0, 0, 0);

        // Separator before table
        doc.setDrawColor(52, 73, 94);
        doc.setLineWidth(0.5);
        doc.line(14, 38, pageWidth - 14, 38);

        // Table headers with proper rupee symbol
        const headers = isDFIA
            ? [['Date', 'Particulars', 'Items', 'CIF $ Dr', 'CIF $ Cr', 'Rate', 'Debit (Rs)', 'Credit (Rs)', 'Balance (Rs)', 'P/L (Rs)']]
            : [['Date', 'Particulars', 'Value Dr', 'Value Cr', 'Rate', 'Debit (Rs)', 'Credit (Rs)', 'Balance (Rs)', 'P/L (Rs)']];

        // Table data with Indian number formatting
        const data = ledger.transactions.map(txn => {
            const row = [
                formatDate(txn.date),
                txn.particular + (txn.invoice_number ? `\n(${txn.invoice_number})` : ''),
            ];

            if (isDFIA) {
                row.push(
                    txn.items || '',
                    txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '',
                    txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : ''
                );
            } else {
                row.push(
                    txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '',
                    txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : ''
                );
            }

            row.push(
                txn.rate ? formatIndianNumber(txn.rate, 2) : '',
                txn.debit_amount ? formatIndianNumber(txn.debit_amount, 2) : '',
                txn.credit_amount ? formatIndianNumber(txn.credit_amount, 2) : '',
                formatIndianNumber(txn.balance, 2),
                txn.type === 'SALE' && txn.profit_loss ? formatIndianNumber(Math.abs(txn.profit_loss), 2) : ''
            );

            return row;
        });

        // Add totals row
        const totalDebit = ledger.transactions.reduce((sum, t) => sum + (t.debit_amount || 0), 0);
        const totalCredit = ledger.transactions.reduce((sum, t) => sum + (t.credit_amount || 0), 0);
        const salesTransactions = ledger.transactions.filter(t => t.type === 'SALE');
        const totalPL = salesTransactions.length > 0 ? salesTransactions[salesTransactions.length - 1].profit_loss : 0;

        const totalsRow = isDFIA
            ? ['', 'TOTAL', '', '', '', '', formatIndianNumber(totalDebit, 2), formatIndianNumber(totalCredit, 2), formatIndianNumber(currentBalance, 2), formatIndianNumber(Math.abs(totalPL), 2)]
            : ['', 'TOTAL', '', '', '', formatIndianNumber(totalDebit, 2), formatIndianNumber(totalCredit, 2), formatIndianNumber(currentBalance, 2), formatIndianNumber(Math.abs(totalPL), 2)];

        data.push(totalsRow);

        autoTable(doc, {
            head: headers,
            body: data,
            startY: 42,
            styles: {
                fontSize: 8.5,
                cellPadding: 3.5,
                lineColor: [224, 224, 224],
                lineWidth: 0.2,
                halign: 'right',
                font: 'helvetica',
                textColor: [44, 62, 80]
            },
            headStyles: {
                fillColor: [52, 73, 94], // Professional dark blue-gray
                fontStyle: 'bold',
                textColor: [255, 255, 255],
                halign: 'center',
                fontSize: 9,
                cellPadding: 4.5,
                lineWidth: 0.3,
                lineColor: [44, 62, 80]
            },
            columnStyles: {
                0: { halign: 'center', cellWidth: 20 }, // Date
                1: { halign: 'left', cellWidth: 45 },   // Particulars
                2: { halign: isDFIA ? 'left' : 'right', cellWidth: isDFIA ? 28 : 18 }, // Items/Value
                3: { halign: 'right', cellWidth: isDFIA ? 24 : 18 },  // CIF $ Dr/Value
                4: { halign: 'right', cellWidth: isDFIA ? 24 : 18 },  // CIF $ Cr/Rate
                5: { halign: 'right', cellWidth: isDFIA ? 18 : 28 },  // Rate/Debit
                6: { halign: 'right', cellWidth: 28 },  // Debit/Credit
                7: { halign: 'right', cellWidth: 28 },  // Credit/Balance
                8: { halign: 'right', cellWidth: 28 },  // Balance/P&L
                9: { halign: 'right', cellWidth: 28 }   // P&L (if DFIA)
            },
            alternateRowStyles: {
                fillColor: [250, 251, 252] // Very light gray for alternate rows
            },
            margin: { left: 14, right: 14 },
            didParseCell: function(data) {
                // Style the totals row with elegant colors
                if (data.row.index === ledger.transactions.length) {
                    data.cell.styles.fillColor = [236, 240, 241]; // Light elegant gray
                    data.cell.styles.fontStyle = 'bold';
                    data.cell.styles.fontSize = 9.5;
                    data.cell.styles.textColor = [25, 42, 86]; // Navy blue
                    data.cell.styles.lineWidth = 0.5;
                    data.cell.styles.lineColor = [52, 73, 94];
                }
            }
        });

        // Professional Footer Section
        const finalY = doc.lastAutoTable.finalY || 42;

        // Footer separator line
        doc.setDrawColor(224, 224, 224);
        doc.setLineWidth(0.3);
        doc.line(14, finalY + 6, pageWidth - 14, finalY + 6);

        // Footer text
        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(127, 140, 141);
        doc.text(`Generated: ${formatDate(new Date())} | License Manager System`, 14, finalY + 11);

        doc.setFont('helvetica', 'bold');
        doc.setTextColor(74, 85, 104);
        doc.text('Page 1 of 1', pageWidth - 14, finalY + 11, { align: 'right' });

        // Save with formatted filename
        const filename = `License_Ledger_${ledger.license_number.replace(/\//g, '-')}_${new Date().toISOString().split('T')[0]}.pdf`;
        doc.save(filename);
    };

    const handleDownloadExcel = () => {
        // Prepare formal Tally-style data with proper formatting
        const data = [];
        let currentRow = 0;

        // Main Title - Professional header
        data.push(['LICENSE LEDGER STATEMENT']);
        currentRow++;

        // License Type subtitle
        data.push([`[ ${ledger.license_type} ]`]);
        currentRow++;

        // Blank row for separation
        data.push([]);
        currentRow++;

        // Section: License Information
        data.push(['LICENSE DETAILS']);
        currentRow++;

        // License details in formal key: value format
        data.push(['License Number:', ledger.license_number, '', '', '', 'License Date:', formatDate(ledger.license_date)]);
        data.push(['Exporter Name:', ledger.exporter || 'N/A', '', '', '', 'Expiry Date:', formatDate(ledger.expiry_date)]);
        data.push(['Total License Value:', formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR'), '', '', '', 'Available Balance:', formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')]);
        currentRow += 3;

        // Separator row
        data.push([]);
        currentRow++;

        // Table headers with proper alignment
        const headers = ['Date', 'Particulars'];
        if (isDFIA) {
            headers.push('Items', 'CIF $ Dr', 'CIF $ Cr');
        } else {
            headers.push('Value Dr', 'Value Cr');
        }
        headers.push('Rate', 'Debit (₹)', 'Credit (₹)', 'Balance (₹)', 'P/L (₹)');
        data.push(headers);
        const headerRow = currentRow;
        currentRow++;

        // Transaction data with proper number formatting
        ledger.transactions.forEach(txn => {
            const row = [
                formatDate(txn.date),
                txn.particular + (txn.invoice_number ? ` (${txn.invoice_number})` : '')
            ];

            if (isDFIA) {
                row.push(
                    txn.items || '',
                    txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '',
                    txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : ''
                );
            } else {
                row.push(
                    txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '',
                    txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : ''
                );
            }

            row.push(
                txn.rate ? formatIndianNumber(txn.rate, 2) : '',
                txn.debit_amount ? formatIndianNumber(txn.debit_amount, 2) : '',
                txn.credit_amount ? formatIndianNumber(txn.credit_amount, 2) : '',
                formatIndianNumber(txn.balance, 2),
                txn.type === 'SALE' && txn.profit_loss ? formatIndianNumber(Math.abs(txn.profit_loss), 2) : ''
            );

            data.push(row);
            currentRow++;
        });

        // Totals row
        const totalDebit = ledger.transactions.reduce((sum, t) => sum + (t.debit_amount || 0), 0);
        const totalCredit = ledger.transactions.reduce((sum, t) => sum + (t.credit_amount || 0), 0);
        const salesTransactions = ledger.transactions.filter(t => t.type === 'SALE');
        const totalPL = salesTransactions.length > 0 ? salesTransactions[salesTransactions.length - 1].profit_loss : 0;

        const totalsRow = ['', 'TOTAL'];
        if (isDFIA) {
            totalsRow.push('', '', '');  // Items, CIF $ Dr, CIF $ Cr
        } else {
            totalsRow.push('', '');
        }
        totalsRow.push('',
            formatIndianNumber(totalDebit, 2),
            formatIndianNumber(totalCredit, 2),
            formatIndianNumber(currentBalance, 2),
            formatIndianNumber(Math.abs(totalPL), 2)
        );
        data.push(totalsRow);
        const totalsRowIndex = currentRow;
        currentRow++;

        // Create worksheet
        const ws = XLSX.utils.aoa_to_sheet(data);

        // Apply Tally-style formatting
        const range = XLSX.utils.decode_range(ws['!ref']);

        // Style main title row (row 0) - Professional header
        if (ws['A1']) {
            ws['A1'].s = {
                font: { bold: true, sz: 16, color: { rgb: "2C3E50" } },
                alignment: { horizontal: 'center', vertical: 'center' },
                fill: { fgColor: { rgb: "ECF0F1" } },
                border: {
                    bottom: { style: 'medium', color: { rgb: "2C3E50" } }
                }
            };
        }

        // Style license type subtitle (row 1)
        if (ws['A2']) {
            ws['A2'].s = {
                font: { bold: true, sz: 12, color: { rgb: "3498DB" } },
                alignment: { horizontal: 'center', vertical: 'center' }
            };
        }

        // Style "LICENSE DETAILS" section header (row 3)
        if (ws['A4']) {
            ws['A4'].s = {
                font: { bold: true, sz: 11, color: { rgb: "FFFFFF" } },
                alignment: { horizontal: 'left', vertical: 'center' },
                fill: { fgColor: { rgb: "34495E" } },
                border: {
                    top: { style: 'thin', color: { rgb: "000000" } },
                    bottom: { style: 'thin', color: { rgb: "000000" } },
                    left: { style: 'thin', color: { rgb: "000000" } },
                    right: { style: 'thin', color: { rgb: "000000" } }
                }
            };
        }

        // Merge title and subtitle across all columns
        ws['!merges'] = ws['!merges'] || [];
        ws['!merges'].push({ s: { r: 0, c: 0 }, e: { r: 0, c: headers.length - 1 } }); // Main title
        ws['!merges'].push({ s: { r: 1, c: 0 }, e: { r: 1, c: headers.length - 1 } }); // Subtitle
        ws['!merges'].push({ s: { r: 3, c: 0 }, e: { r: 3, c: headers.length - 1 } }); // LICENSE DETAILS header

        // Style header row - dark background with white text
        for (let col = 0; col < headers.length; col++) {
            const cellRef = XLSX.utils.encode_cell({ r: headerRow, c: col });
            if (ws[cellRef]) {
                ws[cellRef].s = {
                    font: { bold: true, color: { rgb: "FFFFFF" } },
                    fill: { fgColor: { rgb: "2C3E50" } },
                    border: {
                        top: { style: 'thin', color: { rgb: "000000" } },
                        bottom: { style: 'thin', color: { rgb: "000000" } },
                        left: { style: 'thin', color: { rgb: "000000" } },
                        right: { style: 'thin', color: { rgb: "000000" } }
                    },
                    alignment: { horizontal: 'center', vertical: 'center' }
                };
            }
        }

        // Style totals row - bold with borders
        for (let col = 0; col < headers.length; col++) {
            const cellRef = XLSX.utils.encode_cell({ r: totalsRowIndex, c: col });
            if (ws[cellRef]) {
                ws[cellRef].s = {
                    font: { bold: true },
                    fill: { fgColor: { rgb: "E8E8E8" } },
                    border: {
                        top: { style: 'double', color: { rgb: "000000" } },
                        bottom: { style: 'double', color: { rgb: "000000" } },
                        left: { style: 'thin', color: { rgb: "000000" } },
                        right: { style: 'thin', color: { rgb: "000000" } }
                    },
                    alignment: { horizontal: col > 1 ? 'right' : 'left' }
                };
            }
        }

        // Add borders to all data cells
        for (let row = headerRow + 1; row < totalsRowIndex; row++) {
            for (let col = 0; col < headers.length; col++) {
                const cellRef = XLSX.utils.encode_cell({ r: row, c: col });
                if (ws[cellRef]) {
                    ws[cellRef].s = {
                        border: {
                            top: { style: 'thin', color: { rgb: "CCCCCC" } },
                            bottom: { style: 'thin', color: { rgb: "CCCCCC" } },
                            left: { style: 'thin', color: { rgb: "CCCCCC" } },
                            right: { style: 'thin', color: { rgb: "CCCCCC" } }
                        },
                        alignment: { horizontal: col > 1 ? 'right' : 'left' }
                    };

                    // Number formatting for numeric columns
                    if (col > 2 && ws[cellRef].v !== '') {
                        ws[cellRef].z = '#,##0.00';
                    }
                }
            }
        }

        // Column widths - Tally style
        ws['!cols'] = isDFIA
            ? [
                { wch: 12 },  // Date
                { wch: 40 },  // Particulars
                { wch: 20 },  // Items
                { wch: 14 },  // CIF $ Dr
                { wch: 14 },  // CIF $ Cr
                { wch: 12 },  // Rate
                { wch: 16 },  // Debit
                { wch: 16 },  // Credit
                { wch: 18 },  // Balance
                { wch: 16 }   // P/L
            ]
            : [
                { wch: 12 },  // Date
                { wch: 40 },  // Particulars
                { wch: 14 },  // Value Dr
                { wch: 14 },  // Value Cr
                { wch: 12 },  // Rate
                { wch: 16 },  // Debit
                { wch: 16 },  // Credit
                { wch: 18 },  // Balance
                { wch: 16 }   // P/L
            ];

        // Row heights for better readability and professional appearance
        ws['!rows'] = ws['!rows'] || [];
        ws['!rows'][0] = { hpt: 30 };  // Main title row height
        ws['!rows'][1] = { hpt: 22 };  // Subtitle row height
        ws['!rows'][3] = { hpt: 24 };  // LICENSE DETAILS header row height
        ws['!rows'][headerRow] = { hpt: 25 }; // Table header row height
        ws['!rows'][totalsRowIndex] = { hpt: 24 }; // Totals row height

        // Create workbook and add worksheet
        const wb = XLSX.utils.book_new();
        XLSX.utils.book_append_sheet(wb, ws, 'License Ledger');

        // Download with Tally-style name
        const fileName = `${ledger.license_number.replace(/\//g, '-')}_Ledger_${new Date().toISOString().split('T')[0]}.xlsx`;
        XLSX.writeFile(wb, fileName, { cellStyles: true });
    };

    return (
        <div className="container-fluid" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '0' }}>
            {/* Tally-Style Header */}
            <div style={{
                backgroundColor: '#2c3e50',
                color: 'white',
                padding: '10px 20px',
                borderBottom: '2px solid #34495e'
            }}>
                <div className="d-flex justify-content-between align-items-center">
                    <div>
                        <button
                            className="btn btn-sm btn-outline-light me-3"
                            onClick={() => navigate(-1)}
                            style={{ borderRadius: '2px' }}
                        >
                            ← Back
                        </button>
                        <span style={{ fontSize: '1.1rem', fontWeight: '500' }}>License Ledger</span>
                    </div>
                    <div>
                        <button
                            className="btn btn-sm btn-danger me-2"
                            onClick={handleDownloadPDF}
                            style={{ borderRadius: '2px' }}
                        >
                            <i className="bi bi-file-pdf me-2"></i>
                            Download PDF
                        </button>
                        <button
                            className="btn btn-sm btn-success me-3"
                            onClick={handleDownloadExcel}
                            style={{ borderRadius: '2px' }}
                        >
                            <i className="bi bi-file-excel me-2"></i>
                            Download Excel
                        </button>
                        <span style={{ fontSize: '0.9rem' }}>
                            {formatDate(new Date())}
                        </span>
                    </div>
                </div>
            </div>

            {/* Purchase Warning Alert */}
            {showPurchaseWarning && (
                <div style={{
                    backgroundColor: '#fff3cd',
                    border: '1px solid #ffc107',
                    borderLeft: '5px solid #ffc107',
                    padding: '15px 20px',
                    margin: '0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '15px'
                }}>
                    <i className="bi bi-exclamation-triangle-fill" style={{ fontSize: '1.5rem', color: '#856404' }}></i>
                    <div>
                        <strong style={{ color: '#856404', display: 'block', marginBottom: '5px' }}>
                            ⚠️ Action Required
                        </strong>
                        <span style={{ color: '#856404' }}>
                            {!hasPurchases && isNegativeBalance &&
                                'No purchase transactions found and balance is negative. Please add purchase entries to maintain proper accounting.'}
                            {!hasPurchases && !isNegativeBalance &&
                                'No purchase transactions found. Please add purchase entries for this license.'}
                            {hasPurchases && isNegativeBalance &&
                                `Balance is negative (${formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}). Please add purchase transactions to cover the deficit.`}
                        </span>
                    </div>
                </div>
            )}

            {/* Professional License Header */}
            <div style={{
                backgroundColor: 'white',
                border: '1px solid #dee2e6',
                borderTop: 'none',
                padding: '25px 30px',
                boxShadow: '0 2px 4px rgba(0,0,0,0.05)'
            }}>
                <div className="row align-items-center">
                    <div className="col-md-8">
                        <h4 style={{ marginBottom: '15px', color: '#2c3e50', fontWeight: '600' }}>
                            {ledger.license_number}
                            <span style={{
                                marginLeft: '15px',
                                fontSize: '0.75rem',
                                padding: '4px 12px',
                                backgroundColor: isDFIA ? '#007bff' : '#17a2b8',
                                color: 'white',
                                borderRadius: '4px',
                                fontWeight: '500'
                            }}>
                                {ledger.license_type}
                            </span>
                        </h4>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.95rem' }}>
                            <div>
                                <span style={{ color: '#6c757d', marginRight: '10px' }}>Exporter:</span>
                                <strong>{ledger.exporter || 'N/A'}</strong>
                            </div>
                            <div>
                                <span style={{ color: '#6c757d', marginRight: '10px' }}>License Date:</span>
                                <strong>{formatDate(ledger.license_date)}</strong>
                            </div>
                            {isDFIA && (
                                <div>
                                    <span style={{ color: '#6c757d', marginRight: '10px' }}>SION Norms:</span>
                                    <strong style={{ color: '#17a2b8' }}>
                                        {(() => {
                                            const allNorms = [...new Set(
                                                ledger.transactions
                                                    .filter(t => t.sion_norms)
                                                    .flatMap(t => t.sion_norms.split(', '))
                                            )];
                                            return allNorms.length > 0 ? allNorms.join(', ') : 'N/A';
                                        })()}
                                    </strong>
                                </div>
                            )}
                            <div>
                                <span style={{ color: '#6c757d', marginRight: '10px' }}>Expiry Date:</span>
                                <strong>{formatDate(ledger.expiry_date)}</strong>
                            </div>
                            <div>
                                <span style={{ color: '#6c757d', marginRight: '10px' }}>Total Value:</span>
                                <strong style={{ color: '#007bff' }}>
                                    {formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR')}
                                </strong>
                            </div>
                        </div>
                    </div>
                    <div className="col-md-4 text-end">
                        <div style={{
                            padding: '20px',
                            backgroundColor: '#f8f9fa',
                            borderRadius: '8px',
                            border: '2px solid #e9ecef'
                        }}>
                            <div style={{ fontSize: '0.85rem', color: '#6c757d', marginBottom: '8px', fontWeight: '500' }}>
                                CURRENT BALANCE
                            </div>
                            <div style={{
                                fontSize: '1.75rem',
                                fontWeight: '700',
                                color: currentBalance >= 0 ? '#28a745' : '#dc3545'
                            }}>
                                {formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Professional Ledger Table */}
            <div style={{
                backgroundColor: 'white',
                border: '1px solid #dee2e6',
                borderRadius: '8px',
                marginTop: '20px',
                marginLeft: '20px',
                marginRight: '20px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.08)',
                overflow: 'hidden'
            }}>
                <div style={{
                    backgroundColor: '#f8f9fa',
                    padding: '15px 20px',
                    borderBottom: '2px solid #dee2e6'
                }}>
                    <h5 style={{ margin: '0', color: '#2c3e50', fontWeight: '600' }}>
                        <i className="bi bi-journal-text me-2"></i>
                        Transaction Ledger
                    </h5>
                </div>
                <table style={{
                    width: '100%',
                    borderCollapse: 'collapse',
                    fontSize: '0.9rem'
                }}>
                    {/* Header */}
                    <thead>
                        <tr style={{
                            backgroundColor: '#2c3e50',
                            color: 'white',
                            borderBottom: '2px solid #1a252f'
                        }}>
                            <th style={{ padding: '12px 15px', textAlign: 'left', borderRight: '1px solid #3d4f5f', width: '100px', fontWeight: '600' }}>Date</th>
                            <th style={{ padding: '12px 15px', textAlign: 'left', borderRight: '1px solid #3d4f5f', minWidth: '280px', fontWeight: '600' }}>Particulars</th>
                            {isDFIA && <th style={{ padding: '12px 15px', textAlign: 'left', borderRight: '1px solid #3d4f5f', minWidth: '180px', fontWeight: '600' }}>Items</th>}
                            {isDFIA && <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '110px', fontWeight: '600' }}>CIF $ Dr</th>}
                            {isDFIA && <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '110px', fontWeight: '600' }}>CIF $ Cr</th>}
                            {!isDFIA && <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '120px', fontWeight: '600' }}>Value Dr</th>}
                            {!isDFIA && <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '120px', fontWeight: '600' }}>Value Cr</th>}
                            <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '90px', fontWeight: '600' }}>Rate</th>
                            <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '130px', fontWeight: '600' }}>Debit (₹)</th>
                            <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '130px', fontWeight: '600' }}>Credit (₹)</th>
                            <th style={{ padding: '12px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f', width: '130px', fontWeight: '600' }}>Balance</th>
                            <th style={{ padding: '12px 15px', textAlign: 'right', width: '120px', fontWeight: '600' }}>P/L</th>
                        </tr>
                    </thead>
                    <tbody>
                        {ledger.transactions.map((txn, index) => {
                            const profitLoss = txn.profit_loss || 0;
                            const isProfitable = profitLoss > 0;
                            const isLoss = profitLoss < 0;
                            const isOpening = txn.type === 'OPENING';
                            const isPurchase = txn.type === 'PURCHASE';
                            const isSale = txn.type === 'SALE';

                            return (
                                <tr key={index} style={{
                                    backgroundColor: index % 2 === 0 ? 'white' : '#f8f9fa',
                                    borderBottom: '1px solid #e9ecef',
                                    transition: 'background-color 0.2s'
                                }}
                                onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#e3f2fd'}
                                onMouseLeave={(e) => e.currentTarget.style.backgroundColor = index % 2 === 0 ? 'white' : '#f8f9fa'}
                                >
                                    <td style={{
                                        padding: '12px 15px',
                                        borderRight: '1px solid #e9ecef',
                                        fontWeight: isOpening ? '600' : 'normal',
                                        color: '#495057'
                                    }}>
                                        {formatDate(txn.date)}
                                    </td>
                                    <td style={{
                                        padding: '12px 15px',
                                        borderRight: '1px solid #e9ecef',
                                        fontWeight: isOpening ? '600' : 'normal'
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            {isOpening && <span style={{ color: '#17a2b8', fontSize: '0.9rem' }}>●</span>}
                                            {isPurchase && <span style={{ color: '#ffc107', fontSize: '0.9rem' }}>●</span>}
                                            {isSale && <span style={{ color: '#28a745', fontSize: '0.9rem' }}>●</span>}
                                            <div>
                                                <div style={{ color: '#212529' }}>{txn.particular}</div>
                                                {txn.invoice_number && (
                                                    <div style={{ fontSize: '0.8rem', color: '#6c757d', marginTop: '3px' }}>
                                                        Invoice: {txn.invoice_number}
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    </td>
                                    {isDFIA && (
                                        <td style={{
                                            padding: '12px 15px',
                                            borderRight: '1px solid #e9ecef',
                                            fontSize: '0.85rem',
                                            color: '#495057'
                                        }}>
                                            {txn.items || '-'}
                                        </td>
                                    )}
                                    {isDFIA && (
                                        <>
                                            <td style={{
                                                padding: '12px 15px',
                                                textAlign: 'right',
                                                borderRight: '1px solid #e9ecef',
                                                color: txn.debit_cif ? '#dc3545' : '#6c757d',
                                                fontWeight: txn.debit_cif ? '500' : 'normal'
                                            }}>
                                                {txn.debit_cif ? formatIndianNumber(txn.debit_cif, 2) : '-'}
                                            </td>
                                            <td style={{
                                                padding: '12px 15px',
                                                textAlign: 'right',
                                                borderRight: '1px solid #e9ecef',
                                                color: txn.credit_cif ? '#28a745' : '#6c757d',
                                                fontWeight: txn.credit_cif ? '500' : 'normal'
                                            }}>
                                                {txn.credit_cif ? formatIndianNumber(txn.credit_cif, 2) : '-'}
                                            </td>
                                        </>
                                    )}
                                    {!isDFIA && (
                                        <>
                                            <td style={{
                                                padding: '12px 15px',
                                                textAlign: 'right',
                                                borderRight: '1px solid #e9ecef',
                                                color: txn.debit_license_value ? '#dc3545' : '#6c757d',
                                                fontWeight: txn.debit_license_value ? '500' : 'normal'
                                            }}>
                                                {txn.debit_license_value ? formatIndianNumber(txn.debit_license_value, 2) : '-'}
                                            </td>
                                            <td style={{
                                                padding: '12px 15px',
                                                textAlign: 'right',
                                                borderRight: '1px solid #e9ecef',
                                                color: txn.credit_license_value ? '#28a745' : '#6c757d',
                                                fontWeight: txn.credit_license_value ? '500' : 'normal'
                                            }}>
                                                {txn.credit_license_value ? formatIndianNumber(txn.credit_license_value, 2) : '-'}
                                            </td>
                                        </>
                                    )}
                                    <td style={{
                                        padding: '12px 15px',
                                        textAlign: 'right',
                                        borderRight: '1px solid #e9ecef',
                                        color: '#495057'
                                    }}>
                                        {txn.rate ? formatIndianNumber(txn.rate, 2) : '-'}
                                    </td>
                                    <td style={{
                                        padding: '12px 15px',
                                        textAlign: 'right',
                                        borderRight: '1px solid #e9ecef',
                                        color: txn.debit_amount ? '#dc3545' : '#6c757d',
                                        fontWeight: txn.debit_amount ? '600' : 'normal'
                                    }}>
                                        {txn.debit_amount ? formatIndianNumber(txn.debit_amount, 2) : '-'}
                                    </td>
                                    <td style={{
                                        padding: '12px 15px',
                                        textAlign: 'right',
                                        borderRight: '1px solid #e9ecef',
                                        color: txn.credit_amount ? '#28a745' : '#6c757d',
                                        fontWeight: txn.credit_amount ? '600' : 'normal'
                                    }}>
                                        {txn.credit_amount ? formatIndianNumber(txn.credit_amount, 2) : '-'}
                                    </td>
                                    <td style={{
                                        padding: '12px 15px',
                                        textAlign: 'right',
                                        fontWeight: '700',
                                        backgroundColor: '#f1f3f5',
                                        color: '#212529',
                                        borderRight: '1px solid #e9ecef'
                                    }}>
                                        {formatIndianNumber(txn.balance, 2)}
                                    </td>
                                    <td style={{
                                        padding: '12px 15px',
                                        textAlign: 'right',
                                        fontWeight: '700',
                                        color: isProfitable ? '#28a745' : isLoss ? '#dc3545' : '#6c757d'
                                    }}>
                                        {txn.type === 'SALE' && profitLoss !== 0 ? (
                                            <>
                                                {isProfitable ? '+ ' : '- '}
                                                {formatIndianNumber(Math.abs(profitLoss), 2)}
                                            </>
                                        ) : '-'}
                                    </td>
                                </tr>
                            );
                        })}

                        {/* Totals Row */}
                        <tr style={{
                            backgroundColor: '#34495e',
                            color: 'white',
                            fontWeight: '700',
                            borderTop: '2px solid #2c3e50'
                        }}>
                            <td colSpan="2" style={{ padding: '8px 10px', textAlign: 'right', borderRight: '1px solid #2c3e50' }}>
                                TOTAL
                            </td>
                            {isDFIA && <td style={{ borderRight: '1px solid #2c3e50' }}></td>}
                            {isDFIA && (
                                <>
                                    <td style={{ padding: '8px 10px', textAlign: 'right', borderRight: '1px solid #2c3e50' }}>
                                        {formatIndianNumber(
                                            ledger.transactions.reduce((sum, t) => sum + (t.debit_cif || 0), 0),
                                            2
                                        )}
                                    </td>
                                    <td style={{ padding: '8px 10px', textAlign: 'right', borderRight: '1px solid #2c3e50' }}>
                                        {formatIndianNumber(
                                            ledger.transactions.reduce((sum, t) => sum + (t.credit_cif || 0), 0),
                                            2
                                        )}
                                    </td>
                                </>
                            )}
                            {!isDFIA && (
                                <>
                                    <td style={{ padding: '8px 10px', textAlign: 'right', borderRight: '1px solid #2c3e50' }}>
                                        {formatIndianNumber(
                                            ledger.transactions.reduce((sum, t) => sum + (t.debit_license_value || 0), 0),
                                            2
                                        )}
                                    </td>
                                    <td style={{ padding: '8px 10px', textAlign: 'right', borderRight: '1px solid #2c3e50' }}>
                                        {formatIndianNumber(
                                            ledger.transactions.reduce((sum, t) => sum + (t.credit_license_value || 0), 0),
                                            2
                                        )}
                                    </td>
                                </>
                            )}
                            <td style={{ borderRight: '1px solid #2c3e50' }}></td>
                            <td style={{ padding: '8px 10px', textAlign: 'right', borderRight: '1px solid #2c3e50' }}>
                                {formatIndianNumber(
                                    ledger.transactions.reduce((sum, t) => sum + (t.debit_amount || 0), 0),
                                    2
                                )}
                            </td>
                            <td style={{ padding: '8px 10px', textAlign: 'right', borderRight: '1px solid #2c3e50' }}>
                                {formatIndianNumber(
                                    ledger.transactions.reduce((sum, t) => sum + (t.credit_amount || 0), 0),
                                    2
                                )}
                            </td>
                            <td style={{ padding: '15px 15px', textAlign: 'right', borderRight: '1px solid #3d4f5f' }}>
                                <div style={{ display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '8px' }}>
                                    <span style={{ color: '#adb5bd' }}>Closing:</span>
                                    <span style={{ color: currentBalance >= 0 ? '#51cf66' : '#ff6b6b' }}>
                                        {formatIndianNumber(currentBalance, 2)}
                                    </span>
                                </div>
                            </td>
                            <td style={{ padding: '15px 15px', textAlign: 'right' }}>
                                {(() => {
                                    const salesTransactions = ledger.transactions.filter(t => t.type === 'SALE');
                                    const totalPL = salesTransactions.length > 0
                                        ? salesTransactions[salesTransactions.length - 1].profit_loss
                                        : 0;
                                    return (
                                        <span style={{ color: totalPL >= 0 ? '#51cf66' : '#ff6b6b' }}>
                                            {totalPL >= 0 ? '+ ' : '- '}
                                            {formatIndianNumber(Math.abs(totalPL), 2)}
                                        </span>
                                    );
                                })()}
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>

            {/* Summary Footer - Tally Style */}
            <div style={{
                backgroundColor: 'white',
                border: '1px solid #dee2e6',
                marginTop: '20px',
                marginLeft: '20px',
                marginRight: '20px',
                marginBottom: '20px',
                padding: '15px'
            }}>
                <div className="row text-center" style={{ fontFamily: 'monospace' }}>
                    <div className="col-3">
                        <div style={{ color: '#6c757d', fontSize: '0.75rem', marginBottom: '5px' }}>TRANSACTIONS</div>
                        <div style={{ fontSize: '1.1rem', fontWeight: '700' }}>
                            {ledger.transactions.length - 1}
                        </div>
                    </div>
                    <div className="col-3">
                        <div style={{ color: '#6c757d', fontSize: '0.75rem', marginBottom: '5px' }}>PURCHASES</div>
                        <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#856404' }}>
                            {ledger.transactions.filter(t => t.type === 'PURCHASE').length}
                        </div>
                    </div>
                    <div className="col-3">
                        <div style={{ color: '#6c757d', fontSize: '0.75rem', marginBottom: '5px' }}>SALES</div>
                        <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#155724' }}>
                            {ledger.transactions.filter(t => t.type === 'SALE').length}
                        </div>
                    </div>
                    <div className="col-3">
                        <div style={{ color: '#6c757d', fontSize: '0.75rem', marginBottom: '5px' }}>NET PROFIT/LOSS</div>
                        <div style={{
                            fontSize: '1.1rem',
                            fontWeight: '700',
                            color: (() => {
                                const salesTransactions = ledger.transactions.filter(t => t.type === 'SALE');
                                const lastProfit = salesTransactions.length > 0
                                    ? salesTransactions[salesTransactions.length - 1].profit_loss
                                    : 0;
                                return lastProfit >= 0 ? '#28a745' : '#dc3545';
                            })()
                        }}>
                            {(() => {
                                const salesTransactions = ledger.transactions.filter(t => t.type === 'SALE');
                                const lastProfit = salesTransactions.length > 0
                                    ? salesTransactions[salesTransactions.length - 1].profit_loss
                                    : 0;
                                return (lastProfit >= 0 ? '+ ' : '- ') + formatIndianNumber(Math.abs(lastProfit), 2);
                            })()}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
