// Per-item licence condition badge. Shown next to a LicenseImportItemsModel
// serial number wherever it appears (License form, BOE rows, Allotment items,
// Trade lines, reports). Driven by the `condition_type` field on the row.
//
// Values come from the DFIA parser's condition-sheet extraction:
//   "AU"  — Actual User (item is non-transferable for this licence)
//   "2%"  / "3%" / "5%" / "10%" — CIF capped at N% of total licence CIF
//
// Anything else passes through as a generic grey badge with the raw value.

const CONDITION_BADGE_STYLES = {
    "AU":  { bg: "#DBEAFE", color: "#1E3A8A", label: "AU" },
    "2%":  { bg: "#FEE2E2", color: "#7F1D1D", label: "2%" },
    "3%":  { bg: "#FED7AA", color: "#7C2D12", label: "3%" },
    "5%":  { bg: "#FEF3C7", color: "#78350F", label: "5%" },
    "10%": { bg: "#D1FAE5", color: "#065F46", label: "10%" },
};

export default function ConditionBadge({ type, size = "sm" }) {
    if (!type) return null;
    const style = CONDITION_BADGE_STYLES[type] || {
        bg: "#E5E7EB", color: "#374151", label: type,
    };
    const sized = size === "xs"
        ? { fontSize: "0.6rem", padding: "1px 4px" }
        : { fontSize: "0.65rem", padding: "2px 6px" };
    return (
        <span
            title={type === "AU"
                ? "Actual-user condition (non-transferable for this item)"
                : `Restricted: CIF shall not exceed ${type} of total licence CIF`}
            style={{
                display: "inline-flex",
                alignItems: "center",
                background: style.bg,
                color: style.color,
                fontWeight: 700,
                borderRadius: 4,
                marginLeft: 6,
                lineHeight: 1.2,
                whiteSpace: "nowrap",
                ...sized,
            }}
        >{style.label}</span>
    );
}
