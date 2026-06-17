import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import ExcelJS from 'exceljs';
import { formatIndianNumber } from './numberFormatter';
import { formatDate } from './dateFormatter';

// ─── helpers ────────────────────────────────────────────────────────────────

export function groupByCompany(transactions) {
    const map = {};
    (transactions || []).forEach(txn => {
        const key = txn.company_id != null ? String(txn.company_id) : 'unknown';
        if (!map[key]) {
            map[key] = { company_id: txn.company_id, company_name: txn.company_name || 'N/A', transactions: [] };
        }
        map[key].transactions.push(txn);
    });
    return Object.values(map);
}

const TXN_ORDER = { OPENING: 0, PURCHASE: 1, SALE: 2 };
const sortTxns = (txns) => [...txns].sort((a, b) => (TXN_ORDER[a.type] ?? 1) - (TXN_ORDER[b.type] ?? 1));

function fmtDate(d) { return d ? (formatDate(d) || String(d)) : '-'; }
function fmtNum(v, dp = 2) { return v != null && v !== '' && v !== 0 ? formatIndianNumber(v, dp) : '-'; }
function fmtCur(v, currency = 'INR') {
    if (v == null) return '-';
    const sym = currency === 'USD' ? '$' : 'Rs.';
    return `${sym}${formatIndianNumber(v, 2)}`;
}

// ─── PDF ────────────────────────────────────────────────────────────────────

function computeBalanceMap(license) {
    const isDFIA = license.license_type === 'DFIA';
    const balMap = new Map();

    // Group by company so each company gets its own running balance
    const byCompany = {};
    (license.transactions || []).forEach(txn => {
        const key = txn.company_id != null ? String(txn.company_id) : 'unknown';
        if (!byCompany[key]) byCompany[key] = [];
        byCompany[key].push(txn);
    });

    Object.values(byCompany).forEach(companyTxns => {
        const sorted = sortTxns(companyTxns);
        let running = 0;
        for (const txn of sorted) {
            if (txn.type === 'PURCHASE' || txn.type === 'OPENING') {
                running += isDFIA ? (txn.debit_cif || 0) : (txn.debit_license_value || 0);
            } else if (txn.type === 'SALE') {
                running -= isDFIA ? (txn.credit_cif || 0) : (txn.credit_license_value || 0);
            }
            balMap.set(txn, running);
        }
    });

    return balMap;
}

function buildPdfBody(license, companiesGrouped) {
    const isDFIA = license.license_type === 'DFIA';
    const colCount = isDFIA ? 10 : 9;
    const labelColSpan = isDFIA ? 6 : 5;
    const body = [];
    const balMap = computeBalanceMap(license);

    const chStyle = {
        fillColor: [30, 58, 95], textColor: [255, 255, 255],
        fontStyle: 'bold', fontSize: 9, halign: 'left',
        cellPadding: { top: 5, bottom: 5, left: 8, right: 4 },
    };
    const trStyle = {
        fillColor: [44, 62, 80], textColor: [255, 255, 255],
        fontStyle: 'bold', fontSize: 8.5, halign: 'right',
    };

    companiesGrouped.forEach(company => {
        body.push([{ content: company.company_name, colSpan: colCount, styles: chStyle }]);

        const sortedTxns = sortTxns(company.transactions);
        sortedTxns.forEach(txn => {
            const row = [
                fmtDate(txn.date),
                txn.particular + (txn.invoice_number ? `\n(${txn.invoice_number})` : ''),
            ];
            if (isDFIA) {
                row.push(txn.items || '-', fmtNum(txn.debit_cif), fmtNum(txn.credit_cif));
            } else {
                row.push(fmtNum(txn.debit_license_value), fmtNum(txn.credit_license_value));
            }
            row.push(
                fmtNum(txn.rate),
                txn.debit_amount ? fmtNum(txn.debit_amount) : '-',
                txn.credit_amount ? fmtNum(txn.credit_amount) : '-',
                fmtNum(balMap.get(txn) ?? 0),
                txn.type === 'SALE' && txn.profit_loss != null ? fmtNum(Math.abs(txn.profit_loss)) : '-',
            );
            body.push(row);
        });

        const txns = company.transactions;
        const totalDebit = txns.reduce((s, t) => s + (t.debit_amount || 0), 0);
        const totalCredit = txns.reduce((s, t) => s + (t.credit_amount || 0), 0);
        const companyPL = txns.filter(t => t.type === 'SALE').reduce((s, t) => s + (t.profit_loss || 0), 0);
        const sortedTxns2 = sortTxns(txns);
        const lastBal = sortedTxns2.length > 0 ? (balMap.get(sortedTxns2[sortedTxns2.length - 1]) ?? 0) : 0;

        body.push([
            { content: `Total — ${company.company_name}`, colSpan: labelColSpan, styles: trStyle },
            { content: fmtNum(totalDebit), styles: trStyle },
            { content: fmtNum(totalCredit), styles: trStyle },
            { content: fmtNum(lastBal), styles: trStyle },
            { content: companyPL !== 0 ? fmtNum(Math.abs(companyPL)) : '-', styles: trStyle },
        ]);
    });

    return { body };
}

function writeLicenseHeaderToPdf(doc, license, pageWidth, startY = 12) {
    const isDFIA = license.license_type === 'DFIA';
    const currentBalance = license.available_balance ?? 0;

    // Title
    doc.setFontSize(18);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(25, 42, 86);
    doc.text('LICENSE LEDGER STATEMENT', pageWidth / 2, startY, { align: 'center' });

    doc.setFontSize(10);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(41, 128, 185);
    doc.text(`[ ${license.license_type} ]`, pageWidth / 2, startY + 6, { align: 'center' });

    doc.setDrawColor(200, 210, 220);
    doc.setLineWidth(0.4);
    doc.line(14, startY + 10, pageWidth - 14, startY + 10);

    // Details
    doc.setFontSize(8.5);
    const lx = 14, ry = startY + 16;
    const cols = [
        ['License Number:', String(license.license_number || '-')],
        ['License Date:', fmtDate(license.license_date)],
        ['Expiry Date:', fmtDate(license.expiry_date)],
    ];
    const col2 = [
        ['Exporter:', (license.exporter || 'N/A').substring(0, 40)],
        ['Total Value:', fmtCur(license.total_value, isDFIA ? 'USD' : 'INR')],
        ['Balance:', `$${formatIndianNumber(currentBalance, 2)}`],
    ];

    const colW = (pageWidth - 28) / 2;
    [[cols, 0], [col2, colW]].forEach(([items, xOff]) => {
        items.forEach(([label, val], i) => {
            doc.setFont('helvetica', 'normal');
            doc.setTextColor(100, 116, 139);
            doc.text(label, lx + xOff, ry + i * 6);
            doc.setFont('helvetica', 'bold');
            const isBalance = label === 'Balance:';
            if (isBalance) {
                doc.setTextColor(currentBalance >= 0 ? 22 : 231, currentBalance >= 0 ? 160 : 76, currentBalance >= 0 ? 133 : 60);
            } else {
                doc.setTextColor(17, 24, 39);
            }
            doc.text(val, lx + xOff + 32, ry + i * 6);
        });
    });
    doc.setTextColor(0, 0, 0);

    doc.setDrawColor(200, 210, 220);
    doc.line(14, startY + 36, pageWidth - 14, startY + 36);

    return startY + 40; // return tableStartY
}

function writeSummaryPageToPdf(doc, licensesData) {
    const pageWidth = doc.internal.pageSize.getWidth();

    // Build company → entries map
    const companyMap = new Map();
    for (const license of licensesData) {
        for (const company of groupByCompany(license.transactions)) {
            if (!companyMap.has(company.company_name)) companyMap.set(company.company_name, []);
            const txns = company.transactions;
            companyMap.get(company.company_name).push({
                license,
                totalPurchase: txns.filter(t => t.type === 'PURCHASE' || t.type === 'OPENING').reduce((s, t) => s + (t.debit_amount || 0), 0),
                totalSale: txns.filter(t => t.type === 'SALE').reduce((s, t) => s + (t.credit_amount || 0), 0),
                pl: txns.filter(t => t.type === 'SALE').reduce((s, t) => s + (t.profit_loss || 0), 0),
            });
        }
    }

    // Title
    doc.setFontSize(18); doc.setFont('helvetica', 'bold'); doc.setTextColor(25, 42, 86);
    doc.text('LICENSE LEDGER SUMMARY', pageWidth / 2, 14, { align: 'center' });
    doc.setDrawColor(200, 210, 220); doc.setLineWidth(0.4);
    doc.line(14, 20, pageWidth - 14, 20);

    // Build table body
    const summaryHeaders = [['License Number', 'Type', 'Date', 'Balance ($)', 'Purchase (Rs)', 'Sale (Rs)', 'P/L (Rs)']];
    const summaryBody = [];
    const companyHeaderIdxs = new Set();
    const totalRowIdxs = new Set();
    const licenseUrlMap = {}; // row index → url

    for (const [companyName, entries] of companyMap) {
        companyHeaderIdxs.add(summaryBody.length);
        summaryBody.push([{ content: companyName, colSpan: 7, styles: { fillColor: [30, 58, 95], textColor: [255, 255, 255], fontStyle: 'bold', fontSize: 9, halign: 'left', cellPadding: { top: 4, bottom: 4, left: 8, right: 4 } } }]);

        let companyPurchase = 0, companySale = 0, companyPL = 0;
        for (const { license, totalPurchase, totalSale, pl } of entries) {
            const rowIdx = summaryBody.length;
            if (license.id) licenseUrlMap[rowIdx] = `${window.location.origin}/license-ledger/${license.id}`;
            summaryBody.push([
                license.license_number,
                license.license_type,
                fmtDate(license.license_date),
                `$${formatIndianNumber(license.available_balance ?? 0, 2)}`,
                fmtNum(totalPurchase),
                fmtNum(totalSale),
                pl !== 0 ? fmtNum(Math.abs(pl)) : '-',
            ]);
            companyPurchase += totalPurchase; companySale += totalSale; companyPL += pl;
        }

        totalRowIdxs.add(summaryBody.length);
        summaryBody.push([
            { content: `Total — ${companyName}`, colSpan: 4, styles: { fillColor: [44, 62, 80], textColor: [255, 255, 255], fontStyle: 'bold', halign: 'right' } },
            { content: fmtNum(companyPurchase), styles: { fillColor: [44, 62, 80], textColor: [255, 255, 255], fontStyle: 'bold', halign: 'right' } },
            { content: fmtNum(companySale), styles: { fillColor: [44, 62, 80], textColor: [255, 255, 255], fontStyle: 'bold', halign: 'right' } },
            { content: companyPL !== 0 ? fmtNum(Math.abs(companyPL)) : '-', styles: { fillColor: [44, 62, 80], textColor: [255, 255, 255], fontStyle: 'bold', halign: 'right' } },
        ]);
    }

    autoTable(doc, {
        head: summaryHeaders,
        body: summaryBody,
        startY: 24,
        styles: { fontSize: 8, cellPadding: 3, lineColor: [224, 224, 224], lineWidth: 0.2, halign: 'right', font: 'helvetica', textColor: [44, 62, 80] },
        headStyles: { fillColor: [52, 73, 94], fontStyle: 'bold', textColor: [255, 255, 255], halign: 'center', fontSize: 8.5, cellPadding: 4 },
        columnStyles: {
            0: { halign: 'left', cellWidth: 60 },
            1: { halign: 'center', cellWidth: 20 },
            2: { halign: 'center', cellWidth: 24 },
            3: { halign: 'right', cellWidth: 28 },
            4: { halign: 'right', cellWidth: 34 },
            5: { halign: 'right', cellWidth: 34 },
            6: { halign: 'right', cellWidth: 30 },
        },
        alternateRowStyles: { fillColor: [250, 251, 253] },
        margin: { left: 14, right: 14 },
        didDrawCell: (data) => {
            if (data.section === 'body' && data.column.index === 0 && licenseUrlMap[data.row.index]) {
                doc.link(data.cell.x, data.cell.y, data.cell.width, data.cell.height, { url: licenseUrlMap[data.row.index] });
            }
        },
    });

    const finalY = doc.lastAutoTable.finalY || 24;
    doc.setFontSize(8); doc.setFont('helvetica', 'normal'); doc.setTextColor(127, 140, 141);
    doc.text(`Generated: ${fmtDate(new Date())} | License Manager System`, 14, finalY + 8);
    doc.setFont('helvetica', 'bold'); doc.setTextColor(74, 85, 104);
    doc.text('Page 1 of ' + (licensesData.length + 1), pageWidth - 14, finalY + 8, { align: 'right' });
}

export function generatePDF(licensesData, filename) {
    if (!licensesData?.length) return;

    const doc = new jsPDF('l', 'mm', 'a4');
    const pageWidth = doc.internal.pageSize.getWidth();

    // Summary page first
    writeSummaryPageToPdf(doc, licensesData);

    licensesData.forEach((license, idx) => {
        doc.addPage(); // summary is always page 1

        const isDFIA = license.license_type === 'DFIA';
        const tableStartY = writeLicenseHeaderToPdf(doc, license, pageWidth);

        const companiesGrouped = groupByCompany(license.transactions);
        const { body } = buildPdfBody(license, companiesGrouped);

        const headers = isDFIA
            ? [['Date', 'Particulars', 'Items', 'CIF $ Dr', 'CIF $ Cr', 'Rate', 'Debit (Rs)', 'Credit (Rs)', 'Balance ($)', 'P/L (Rs)']]
            : [['Date', 'Particulars', 'Value Dr ($)', 'Value Cr ($)', 'Rate', 'Debit (Rs)', 'Credit (Rs)', 'Balance ($)', 'P/L (Rs)']];

        autoTable(doc, {
            head: headers,
            body,
            startY: tableStartY,
            styles: {
                fontSize: 8,
                cellPadding: 3,
                lineColor: [224, 224, 224],
                lineWidth: 0.2,
                halign: 'right',
                font: 'helvetica',
                textColor: [44, 62, 80],
            },
            headStyles: {
                fillColor: [52, 73, 94],
                fontStyle: 'bold',
                textColor: [255, 255, 255],
                halign: 'center',
                fontSize: 8.5,
                cellPadding: 4,
            },
            columnStyles: isDFIA ? {
                0: { halign: 'center', cellWidth: 20 },
                1: { halign: 'left', cellWidth: 44 },
                2: { halign: 'left', cellWidth: 24 },
                3: { halign: 'right', cellWidth: 22 },
                4: { halign: 'right', cellWidth: 22 },
                5: { halign: 'right', cellWidth: 16 },
                6: { halign: 'right', cellWidth: 26 },
                7: { halign: 'right', cellWidth: 26 },
                8: { halign: 'right', cellWidth: 26 },
                9: { halign: 'right', cellWidth: 24 },
            } : {
                0: { halign: 'center', cellWidth: 20 },
                1: { halign: 'left', cellWidth: 58 },
                2: { halign: 'right', cellWidth: 24 },
                3: { halign: 'right', cellWidth: 24 },
                4: { halign: 'right', cellWidth: 18 },
                5: { halign: 'right', cellWidth: 30 },
                6: { halign: 'right', cellWidth: 30 },
                7: { halign: 'right', cellWidth: 28 },
                8: { halign: 'right', cellWidth: 26 },
            },
            alternateRowStyles: { fillColor: [250, 251, 253] },
            margin: { left: 14, right: 14 },
        });

        // Footer
        const finalY = doc.lastAutoTable.finalY || tableStartY;
        doc.setDrawColor(200, 210, 220);
        doc.setLineWidth(0.3);
        doc.line(14, finalY + 5, pageWidth - 14, finalY + 5);
        doc.setFontSize(8);
        doc.setFont('helvetica', 'normal');
        doc.setTextColor(127, 140, 141);
        doc.text(`Generated: ${fmtDate(new Date())} | License Manager System`, 14, finalY + 10);
        doc.setFont('helvetica', 'bold');
        doc.setTextColor(74, 85, 104);
        doc.text(`Page ${idx + 2} of ${licensesData.length + 1}`, pageWidth - 14, finalY + 10, { align: 'right' });
    });

    const fname = filename || `License_Ledger_${new Date().toISOString().split('T')[0]}.pdf`;
    doc.save(fname);
}

// ─── Excel summary sheet ─────────────────────────────────────────────────────

function buildSummarySheet(wb, licensesData) {
    const ws = wb.addWorksheet('Summary');
    const COLS = 7;
    const thinBorder = (argb = 'FF000000') => ({ style: 'thin', color: { argb } });
    const allThin = (argb = 'FFDDDDDD') => ({
        top: thinBorder(argb), bottom: thinBorder(argb),
        left: thinBorder(argb), right: thinBorder(argb),
    });

    // Build company → license summary mapping
    const companyMap = new Map();
    for (const license of licensesData) {
        const companies = groupByCompany(license.transactions);
        for (const company of companies) {
            if (!companyMap.has(company.company_name)) companyMap.set(company.company_name, []);
            const txns = company.transactions;
            const totalPurchase = txns.filter(t => t.type === 'PURCHASE' || t.type === 'OPENING')
                .reduce((s, t) => s + (t.debit_amount || 0), 0);
            const totalSale = txns.filter(t => t.type === 'SALE')
                .reduce((s, t) => s + (t.credit_amount || 0), 0);
            const pl = txns.filter(t => t.type === 'SALE')
                .reduce((s, t) => s + (t.profit_loss || 0), 0);
            companyMap.get(company.company_name).push({ license, totalPurchase, totalSale, pl });
        }
    }

    // Title
    ws.addRow(['LICENSE LEDGER SUMMARY']);
    ws.mergeCells(1, 1, 1, COLS);
    Object.assign(ws.getCell(1, 1), {
        font: { bold: true, size: 16, color: { argb: 'FF1A2A56' } },
        alignment: { horizontal: 'center', vertical: 'middle' },
        fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEEF2FA' } },
        border: { bottom: { style: 'medium', color: { argb: 'FF34495E' } } },
    });
    ws.getRow(1).height = 32;
    ws.addRow([]);

    // Column header row
    const headers = ['License Number', 'Type', 'Date', 'Balance ($)', 'Purchase (Rs)', 'Sale (Rs)', 'P/L (Rs)'];
    ws.addRow(headers);
    const hdrRowNum = ws.rowCount;
    for (let col = 1; col <= COLS; col++) {
        Object.assign(ws.getCell(hdrRowNum, col), {
            font: { bold: true, color: { argb: 'FFFFFFFF' } },
            fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF34495E' } },
            alignment: { horizontal: col <= 3 ? 'left' : 'right', vertical: 'middle' },
            border: allThin('FF34495E'),
        });
    }
    ws.getRow(hdrRowNum).height = 22;

    // Per-company sections
    for (const [companyName, entries] of companyMap) {
        // Company header — full width merge
        const chRowNum = ws.rowCount + 1;
        ws.addRow([companyName]);
        ws.mergeCells(chRowNum, 1, chRowNum, COLS);
        Object.assign(ws.getCell(chRowNum, 1), {
            font: { bold: true, size: 10, color: { argb: 'FFFFFFFF' } },
            fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1E3A5F' } },
            alignment: { horizontal: 'left', vertical: 'middle', indent: 1 },
            border: allThin('FF1E3A5F'),
        });
        ws.getRow(chRowNum).height = 22;

        let companyPurchase = 0, companySale = 0, companyPL = 0;

        for (const { license, totalPurchase, totalSale, pl } of entries) {
            const balance = license.available_balance ?? 0;
            const rowNum = ws.rowCount + 1;

            ws.addRow([
                license.license_number,
                license.license_type,
                fmtDate(license.license_date),
                `$${formatIndianNumber(balance, 2)}`,
                fmtNum(totalPurchase),
                fmtNum(totalSale),
                pl !== 0 ? fmtNum(Math.abs(pl)) : '-',
            ]);

            // Hyperlink on license number
            if (license.id) {
                ws.getCell(rowNum, 1).value = {
                    text: String(license.license_number),
                    hyperlink: `${window.location.origin}/license-ledger/${license.id}`,
                    tooltip: `Open ${license.license_number}`,
                };
                ws.getCell(rowNum, 1).font = { color: { argb: 'FF0563C1' }, underline: true, bold: false };
            }

            const plPositive = pl >= 0;
            for (let col = 1; col <= COLS; col++) {
                const cell = ws.getCell(rowNum, col);
                if (col !== 1) cell.font = { color: { argb: col === 7 ? (plPositive ? 'FF065F46' : 'FF991B1B') : 'FF111827' } };
                cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFFFFFFF' } };
                cell.border = allThin();
                cell.alignment = { horizontal: col <= 3 ? 'left' : 'right', vertical: 'middle' };
            }
            ws.getRow(rowNum).height = 18;

            companyPurchase += totalPurchase;
            companySale += totalSale;
            companyPL += pl;
        }

        // Company total row — merge cols 1-4 for label
        const trRowNum = ws.rowCount + 1;
        ws.addRow([`Total — ${companyName}`, '', '', '', fmtNum(companyPurchase), fmtNum(companySale), companyPL !== 0 ? fmtNum(Math.abs(companyPL)) : '-']);
        ws.mergeCells(trRowNum, 1, trRowNum, 4);
        for (let col = 1; col <= COLS; col++) {
            const cell = ws.getCell(trRowNum, col);
            cell.font = { bold: true, color: { argb: col === 7 ? (companyPL >= 0 ? 'FF6EE7B7' : 'FFFCA5A5') : 'FFFFFFFF' } };
            cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF2C3E50' } };
            cell.border = { top: { style: 'medium', color: { argb: 'FF2C3E50' } }, bottom: { style: 'medium', color: { argb: 'FF2C3E50' } }, left: thinBorder(), right: thinBorder() };
            cell.alignment = { horizontal: 'right', vertical: 'middle' };
        }
        ws.getRow(trRowNum).height = 22;
        ws.addRow([]);
    }

    // Column widths
    [30, 12, 14, 16, 18, 18, 16].forEach((w, i) => { ws.getColumn(i + 1).width = w; });
}

// ─── Excel ──────────────────────────────────────────────────────────────────

export async function generateExcel(licensesData, filename) {
    if (!licensesData?.length) return;

    const wb = new ExcelJS.Workbook();
    wb.creator = 'License Manager';
    wb.created = new Date();

    const thinBorder = (argb = 'FF000000') => ({ style: 'thin', color: { argb } });
    const allThin = (argb = 'FF000000') => ({
        top: thinBorder(argb), bottom: thinBorder(argb),
        left: thinBorder(argb), right: thinBorder(argb),
    });

    // Summary sheet first (tab 1)
    buildSummarySheet(wb, licensesData);

    for (const license of licensesData) {
        const isDFIA = license.license_type === 'DFIA';
        const currentBalance = license.available_balance ?? 0;
        const sheetName = String(license.license_number || 'License')
            .replace(/[\\/:*?[\]]/g, '-')
            .substring(0, 31);
        const ws = wb.addWorksheet(sheetName);

        const headers = ['Date', 'Particulars'];
        if (isDFIA) headers.push('Items', 'CIF $ Dr', 'CIF $ Cr');
        else headers.push('Value Dr', 'Value Cr');
        headers.push('Rate', 'Debit (₹)', 'Credit (₹)', isDFIA ? 'Balance ($)' : 'Balance (₹)', 'P/L (₹)');
        const numCols = headers.length;

        // ── Title block
        ws.addRow(['LICENSE LEDGER STATEMENT']);
        ws.mergeCells(1, 1, 1, numCols);
        Object.assign(ws.getCell(1, 1), {
            font: { bold: true, size: 16, color: { argb: 'FF1A2A56' } },
            alignment: { horizontal: 'center', vertical: 'middle' },
            fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEEF2FA' } },
            border: { bottom: { style: 'medium', color: { argb: 'FF34495E' } } },
        });
        ws.getRow(1).height = 32;

        ws.addRow([`[ ${license.license_type} ]`]);
        ws.mergeCells(2, 1, 2, numCols);
        Object.assign(ws.getCell(2, 1), {
            font: { bold: true, size: 11, color: { argb: 'FF2980B9' } },
            alignment: { horizontal: 'center', vertical: 'middle' },
        });
        ws.getRow(2).height = 20;

        ws.addRow([]);

        // ── License detail rows
        const detailRows = [
            ['License Number:', license.license_number || '-', '', '', '', 'License Date:', fmtDate(license.license_date)],
            ['Exporter:', (license.exporter || 'N/A'), '', '', '', 'Expiry Date:', fmtDate(license.expiry_date)],
            ['Total Value:', fmtCur(license.total_value, isDFIA ? 'USD' : 'INR'), '', '', '', 'Balance:', fmtCur(currentBalance, isDFIA ? 'USD' : 'INR')],
        ];
        detailRows.forEach(dr => {
            ws.addRow(dr);
            const rn = ws.rowCount;
            [1, 6].forEach(col => {
                ws.getCell(rn, col).font = { bold: false, color: { argb: 'FF647488' } };
            });
            [2, 7].forEach(col => {
                ws.getCell(rn, col).font = { bold: true, color: { argb: 'FF111827' } };
            });
        });

        ws.addRow([]);

        // ── Column header row
        const headerRowNum = ws.rowCount + 1;
        ws.addRow(headers);
        for (let col = 1; col <= numCols; col++) {
            const cell = ws.getCell(headerRowNum, col);
            cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
            cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF34495E' } };
            cell.alignment = { horizontal: 'center', vertical: 'middle' };
            cell.border = allThin();
        }
        ws.getRow(headerRowNum).height = 24;

        // ── Data rows grouped by company
        const companiesGrouped = groupByCompany(license.transactions);
        const balMap = computeBalanceMap(license);

        for (const company of companiesGrouped) {
            const txns = sortTxns(company.transactions);

            // Company header (merged)
            let rowNum = ws.rowCount + 1;
            ws.addRow([company.company_name]);
            ws.mergeCells(rowNum, 1, rowNum, numCols);
            Object.assign(ws.getCell(rowNum, 1), {
                font: { bold: true, size: 10, color: { argb: 'FFFFFFFF' } },
                fill: { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1E3A5F' } },
                alignment: { horizontal: 'left', vertical: 'middle', indent: 1 },
                border: allThin('FF1E3A5F'),
            });
            ws.getRow(rowNum).height = 22;

            // Transaction rows
            for (const txn of txns) {
                rowNum = ws.rowCount + 1;
                const isPurchase = txn.type === 'PURCHASE' || txn.type === 'OPENING';
                const isSale = txn.type === 'SALE';

                const row = [
                    fmtDate(txn.date),
                    txn.particular + (txn.invoice_number ? ` (${txn.invoice_number})` : ''),
                ];
                if (isDFIA) row.push(txn.items || '', fmtNum(txn.debit_cif), fmtNum(txn.credit_cif));
                else row.push(fmtNum(txn.debit_license_value), fmtNum(txn.credit_license_value));
                row.push(
                    fmtNum(txn.rate),
                    txn.debit_amount ? fmtNum(txn.debit_amount) : '-',
                    txn.credit_amount ? fmtNum(txn.credit_amount) : '-',
                    fmtNum(balMap.get(txn) ?? 0),
                    isSale && txn.profit_loss != null ? fmtNum(Math.abs(txn.profit_loss)) : '-',
                );

                ws.addRow(row);
                const bgArgb = isPurchase ? 'FFF0FDF4' : (isSale ? 'FFFFF4F4' : 'FFFFFFFF');
                for (let col = 1; col <= numCols; col++) {
                    const cell = ws.getCell(rowNum, col);
                    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bgArgb } };
                    cell.border = allThin('FFDDDDDD');
                    const isRight = col > 2 && !(col === 3 && isDFIA);
                    cell.alignment = { horizontal: isRight ? 'right' : 'left', vertical: 'middle', wrapText: col === 2 };
                }
                if (isPurchase) ws.getCell(rowNum, numCols - 2).font = { color: { argb: 'FF065F46' } };
                if (isSale) ws.getCell(rowNum, numCols - 1).font = { color: { argb: 'FF991B1B' } };
            }

            // Company total row
            rowNum = ws.rowCount + 1;
            const totalDebit = txns.reduce((s, t) => s + (t.debit_amount || 0), 0);
            const totalCredit = txns.reduce((s, t) => s + (t.credit_amount || 0), 0);
            const companyPL = txns.filter(t => t.type === 'SALE').reduce((s, t) => s + (t.profit_loss || 0), 0);
            const lastBal = txns.length > 0 ? (balMap.get(txns[txns.length - 1]) ?? 0) : 0;

            const labelMergeCols = isDFIA ? 6 : 5; // 1-indexed: merge cols 1..labelMergeCols
            const totalRowData = new Array(numCols).fill('');
            totalRowData[0] = `Total — ${company.company_name}`; // col 1 (label in merged region)
            totalRowData[numCols - 4] = fmtNum(totalDebit);
            totalRowData[numCols - 3] = fmtNum(totalCredit);
            totalRowData[numCols - 2] = fmtNum(lastBal);
            totalRowData[numCols - 1] = companyPL !== 0 ? fmtNum(Math.abs(companyPL)) : '-';

            ws.addRow(totalRowData);
            ws.mergeCells(rowNum, 1, rowNum, labelMergeCols);
            for (let col = 1; col <= numCols; col++) {
                const cell = ws.getCell(rowNum, col);
                cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
                cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF2C3E50' } };
                cell.border = {
                    top: { style: 'medium', color: { argb: 'FF2C3E50' } },
                    bottom: { style: 'medium', color: { argb: 'FF2C3E50' } },
                    left: thinBorder(),
                    right: thinBorder(),
                };
                cell.alignment = { horizontal: col === 1 ? 'right' : 'right', vertical: 'middle' };
            }
            // color sub-cells
            ws.getCell(rowNum, numCols - 2).font = { bold: true, color: { argb: 'FF93C5FD' } };
            ws.getCell(rowNum, numCols - 1).font = { bold: true, color: { argb: companyPL >= 0 ? 'FF6EE7B7' : 'FFFCA5A5' } };
            ws.getRow(rowNum).height = 22;

            // blank separator
            ws.addRow([]);
        }

        // ── Column widths
        const colWidths = isDFIA
            ? [12, 44, 22, 16, 16, 14, 18, 18, 20, 18]
            : [12, 52, 16, 16, 14, 18, 18, 20, 18];
        colWidths.forEach((w, i) => { ws.getColumn(i + 1).width = w; });
    }

    const buffer = await wb.xlsx.writeBuffer();
    const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `License_Ledger_${new Date().toISOString().split('T')[0]}.xlsx`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}
