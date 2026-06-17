// Pure license-PDF parse transforms extracted verbatim from MasterForm.
// No component state/props — operate only on the passed `data`.

export const buildLicensePatch = (data) => {
    const { parsed = {}, prefill = {}, items = [], item_conditions = [] } = data || {};

    // Build a {serialNumber: conditionType} map from parsed conditions so
    // we can flag restricted rows and surface badges in the UI.
    const conditionBySerial = {};
    for (const c of item_conditions) {
        for (const si of (c.serial_numbers || [])) {
            conditionBySerial[si] = c.type;
        }
    }

    const importRows = (items || []).map((it, idx) => {
        const sn = it.serial_number ?? (idx + 1);
        const cond = conditionBySerial[sn] || "";
        return {
            serial_number: sn,
            hs_code: it.matched_hs_code_id || null,
            description: it.description || "",
            items: [],
            quantity: parseFloat(it.quantity || 0),
            unit: "kg",
            cif_fc: parseFloat(it.cif_fc || 0),
            cif_inr: parseFloat(it.cif_inr || 0),
            is_restricted: Boolean(cond),
            condition_type: cond,
        };
    });

    // Financial totals extracted from the licence header. We don't put
    // these in `patch.export_license` directly — instead we expose them
    // via `exportFinancials` so applyLicenseParse can merge them into the
    // FIRST existing export row (or create one if none exists) without
    // clobbering user-entered Description / Norm Class / Net Quantity.
    const fobInr = parseFloat(parsed.fob_inr || 0);
    const cifInr = parseFloat(parsed.cif_inr || 0);
    const cifFc  = parseFloat(parsed.cif_fc || 0);
    const exportFinancials = (fobInr || cifInr || cifFc)
        ? { fob_inr: fobInr || 0, cif_inr: cifInr || 0, cif_fc: cifFc || 0 }
        : null;

    const patch: Record<string, any> = {};
    if (prefill.license_number) patch.license_number = prefill.license_number;
    if (prefill.license_date) patch.license_date = prefill.license_date;
    if (prefill.license_expiry_date) patch.license_expiry_date = prefill.license_expiry_date;
    if (prefill.file_number) patch.file_number = prefill.file_number;
    if (prefill.registration_number) patch.registration_number = prefill.registration_number;
    if (prefill.registration_date) patch.registration_date = prefill.registration_date;
    if (prefill.notification_number) patch.notification_number = prefill.notification_number;
    if (prefill.scheme_code) patch.scheme_code = prefill.scheme_code;
    if (prefill.exporter) patch.exporter = prefill.exporter;
    if (prefill.port) patch.port = prefill.port;
    if (prefill.condition_sheet) patch.condition_sheet = prefill.condition_sheet;
    if (importRows.length > 0) patch.import_license = importRows;
    return { patch, importRows, conditionBySerial, exportFinancials };
};

export const buildLicenseSummary = (data) => {
    const { parsed = {}, items = [], matched_company_id, matched_company_name,
            company_created, matched_port_id, matched_port_code } = data || {};
    return {
        license_number: parsed.license_number,
        license_date: parsed.license_date,
        license_expiry_date: parsed.license_expiry_date,
        file_number: parsed.file_number,
        port_code: matched_port_code || parsed.port_code,
        notification_number: parsed.notification_number,
        company_name: matched_company_name,
        company_created,
        matched_company_id,
        matched_port_id,
        source_kind: parsed.source_kind,
        items: items || [],
        unmatchedHsn: (items || []).filter(it => !it.matched_hs_code_id).length,
    };
};
