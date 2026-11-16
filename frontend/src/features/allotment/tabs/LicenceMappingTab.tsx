import DetailTable from "@/components/primitives/DetailTable";
import { DetailQueryBoundary } from "../DetailQueryBoundary";
import { displayValue } from "@/lib/display";

const COLUMNS = [
    { key: "license_number", label: "License", bold: true, nowrap: true },
    { key: "serial_number", label: "Sl#", align: "right", nowrap: true },
    { key: "license_date", label: "License Date", nowrap: true },
    { key: "license_expiry", label: "Expiry", nowrap: true },
    { key: "exporter", label: "Exporter" },
    { key: "notification_number", label: "Notification", nowrap: true },
    { key: "file_number", label: "File No.", nowrap: true },
    { key: "port_code", label: "Port", nowrap: true },
    { key: "purchase_status", label: "Purchase", nowrap: true },
    { key: "current_owner", label: "Current Owner" },
    { key: "file_transfer_status", label: "File Transfer", nowrap: true },
].map((c) => ({ ...c, render: (v: unknown) => displayValue(v) }));

/** Licence Mapping: licence metadata of each allotted line from `allotments/:id/`, as received. */
export function LicenceMappingTab({ id }: { id: number }) {
    return (
        <DetailQueryBoundary id={id}>
            {(record) => (
                <DetailTable
                    columns={COLUMNS}
                    rows={record.allotment_details || []}
                    emptyMessage="No licences are mapped to this allotment yet."
                />
            )}
        </DetailQueryBoundary>
    );
}
