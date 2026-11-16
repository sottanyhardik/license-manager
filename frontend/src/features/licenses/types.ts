/** One row of the `licenses/` list endpoint, as consumed by the register card. */
export interface LicenseListItem {
    id: number;
    license_number: string;
    license_date: string | null;
    license_expiry_date: string | null;
    ledger_date: string | null;
    port_name: string | null;
    exporter_name: string | null;
    exporter_iec: string | null;
    get_norm_class: string | null;
    get_balance_cif: string | number | null;
    is_over_utilised?: boolean | null;
    individual_item_cif_override?: boolean | null;
    latest_transfer: string | null;
    purchase_status_label: string | null;
    purchase_status_code: string | null;
    is_manually_planned: boolean;
    has_tl: boolean;
    has_copy: boolean;
    has_condition_sheet: boolean;
    [key: string]: unknown;
}

export interface LicenceTransfer {
    transfer_initiation_date: string | null;
    transfer_acceptance_date: string | null;
    from_iec: string | null;
    from_name: string | null;
    to_iec: string | null;
    to_name: string | null;
    transfer_status: string | null;
}

/** `license-actions/:id/ownership-data/` */
export interface LicenceOwnershipData {
    license_number: string;
    last_ownership_fetch: string | null;
    file_transfer_status: string | null;
    current_owner: { iec: string; name: string; address: string | null } | null;
    transfers: LicenceTransfer[];
}
