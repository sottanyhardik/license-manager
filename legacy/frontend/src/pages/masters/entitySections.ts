// Section + field layout config per master entity.
// Extracted verbatim from MasterForm (pure data, no behavior change).
// `icon` values are Bootstrap-icon names resolved via the shared <Icon> component.

export const ENTITY_SECTIONS = {
    'bill-of-entries': [
        {
            title: 'Document Info',
            icon: 'receipt-cutoff',
            color: 'var(--tb-brand)',
            fields: ['bill_of_entry_number', 'bill_of_entry_date', 'appraisement', 'ooc_date'],
            cols: { bill_of_entry_number: 'col-md-4', bill_of_entry_date: 'col-md-4', appraisement: 'col-md-4', ooc_date: 'col-md-4' },
        },
        {
            title: 'Parties & Location',
            icon: 'building',
            color: 'var(--tb-brand)',
            fields: ['company', 'allotment', 'port', 'cha'],
            cols: { company: 'col-md-4', allotment: 'col-md-4', port: 'col-md-4', cha: 'col-md-4' },
        },
        {
            title: 'Financial',
            icon: 'currency-dollar',
            color: 'var(--tb-success)',
            fields: ['exchange_rate'],
            cols: { exchange_rate: 'col-md-4' },
        },
        {
            title: 'Invoice Details',
            icon: 'file-earmark-text',
            color: 'var(--tb-warning)',
            fields: ['product_name', 'invoice_no', 'invoice_date'],
            cols: { product_name: 'col-md-4', invoice_no: 'col-md-4', invoice_date: 'col-md-4' },
        },
        {
            title: 'Notes',
            icon: 'chat-left-text',
            color: 'var(--tb-text-secondary)',
            fields: ['comments'],
            cols: { comments: 'col-12' },
        },
    ],
    licenses: [
        {
            title: 'License Identification',
            icon: 'file-earmark-text',
            color: 'var(--tb-brand)',
            fields: ['license_number', 'license_date', 'license_expiry_date', 'port', 'iec', 'scheme_code', 'advance_auth_number'],
            cols: { license_number: 'col-md-4', license_date: 'col-md-4', license_expiry_date: 'col-md-4', port: 'col-md-4', iec: 'col-md-4', scheme_code: 'col-md-4', advance_auth_number: 'col-md-4' },
        },
        {
            title: 'Financial Details',
            icon: 'currency-dollar',
            color: 'var(--tb-success)',
            fields: ['total_cif_fc', 'total_cif_inr', 'total_duty_amount', 'exchange_rate', 'duty_rate'],
            cols: { total_cif_fc: 'col-md-4', total_cif_inr: 'col-md-4', total_duty_amount: 'col-md-4', exchange_rate: 'col-md-4', duty_rate: 'col-md-4' },
        },
        {
            title: 'Status Flags',
            icon: 'toggle-on',
            color: 'var(--tb-brand)',
            fields: ['is_expired', 'is_null_dfia', 'is_incentive'],
            cols: { is_expired: 'col-md-4', is_null_dfia: 'col-md-4', is_incentive: 'col-md-4' },
        },
        {
            title: 'Conditions & Notes',
            icon: 'chat-left-text',
            color: 'var(--tb-text-secondary)',
            fields: ['conditions', 'restrictions', 'comments', 'description', 'notes'],
            cols: {},
        },
    ],
    'incentive-licenses': [
        {
            title: 'License Details',
            icon: 'award',
            color: 'var(--tb-warning)',
            fields: ['license_type', 'license_number', 'license_date', 'license_expiry_date'],
            cols: { license_type: 'col-md-3', license_number: 'col-md-3', license_date: 'col-md-3', license_expiry_date: 'col-md-3' },
        },
        {
            title: 'Party & Port',
            icon: 'building',
            color: 'var(--tb-brand)',
            fields: ['exporter', 'port_code'],
            cols: { exporter: 'col-md-6', port_code: 'col-md-6' },
        },
        {
            title: 'Financial',
            icon: 'currency-rupee',
            color: 'var(--tb-success)',
            fields: ['license_value'],
            cols: { license_value: 'col-md-4' },
        },
        {
            title: 'Status & Notes',
            icon: 'toggle-on',
            color: 'var(--tb-text-secondary)',
            fields: ['is_active', 'notes'],
            cols: { is_active: 'col-md-4' },
        },
    ],
    trades: [
        {
            title: 'Trade Details',
            icon: 'arrow-left-right',
            color: 'var(--tb-success)',
            fields: ['direction', 'license_type', 'invoice_number', 'invoice_date'],
            cols: { direction: 'col-md-3', license_type: 'col-md-3', invoice_number: 'col-md-3', invoice_date: 'col-md-3' },
        },
        {
            title: 'Parties',
            icon: 'building',
            color: 'var(--tb-brand)',
            fields: ['from_company', 'to_company'],
            cols: { from_company: 'col-md-6', to_company: 'col-md-6' },
        },
        {
            title: 'References',
            icon: 'link-45deg',
            color: 'var(--tb-brand)',
            fields: ['incentive_license', 'boe'],
            cols: { incentive_license: 'col-md-6', boe: 'col-md-6' },
        },
        {
            title: 'Documents & Notes',
            icon: 'file-earmark-arrow-up',
            color: 'var(--tb-text-secondary)',
            fields: ['purchase_invoice_copy', 'remarks'],
            cols: { purchase_invoice_copy: 'col-md-6' },
        },
    ],
};
