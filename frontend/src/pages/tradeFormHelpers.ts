import { formatDateForInput } from "../utils/dateFormatter";

export function formatTradeDateForApi(date: any): any {
    if (!date) return null;
    if (!(date instanceof Date)) return date;
    return formatDateForInput(date);
}

export function getEntityId(value: any) {
    return typeof value === "object" ? value?.id : value;
}

function removeEmptyId(record: Record<string, any>) {
    if (record.id === "" || record.id === null || record.id === undefined) {
        delete record.id;
    }
    return record;
}

export function cleanTradeLine(line: Record<string, any>) {
    const cleanedLine = removeEmptyId({ ...line });
    if (cleanedLine.sr_number && typeof cleanedLine.sr_number === "object") {
        cleanedLine.sr_number = cleanedLine.sr_number.id;
    }
    cleanedLine.hsn_code = "49070000";
    return cleanedLine;
}

export function cleanIncentiveLine(line: Record<string, any>) {
    const cleanedLine = removeEmptyId({ ...line });
    if (cleanedLine.incentive_license && typeof cleanedLine.incentive_license === "object") {
        cleanedLine.incentive_license = cleanedLine.incentive_license.id;
    }
    return cleanedLine;
}

export function cleanTradePayment(payment: Record<string, any>) {
    return removeEmptyId({
        ...payment,
        date: formatTradeDateForApi(payment.date),
    });
}

export function buildTradeJsonPayload(formData: Record<string, any>, autoCreatePaired: boolean) {
    return {
        direction: formData.direction,
        license_type: formData.license_type,
        from_company: getEntityId(formData.from_company),
        to_company: getEntityId(formData.to_company),
        boe: getEntityId(formData.boe) || null,
        invoice_number: formData.invoice_number?.trim() || "",
        invoice_date: formatTradeDateForApi(formData.invoice_date),
        remarks: formData.remarks || "",
        from_pan: formData.from_pan || "",
        from_gst: formData.from_gst || "",
        from_addr_line_1: formData.from_addr_line_1 || "",
        from_addr_line_2: formData.from_addr_line_2 || "",
        to_pan: formData.to_pan || "",
        to_gst: formData.to_gst || "",
        to_addr_line_1: formData.to_addr_line_1 || "",
        to_addr_line_2: formData.to_addr_line_2 || "",
        lines: (formData.lines || []).map(cleanTradeLine),
        incentive_lines: (formData.incentive_lines || []).map(cleanIncentiveLine),
        payments: (formData.payments || []).map(cleanTradePayment),
        auto_create_paired: autoCreatePaired,
    };
}
