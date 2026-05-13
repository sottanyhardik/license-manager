/**
 * DetailTable — clean, readable table for the expanded detail area of an
 * EntityCard. Wraps the table in a horizontal-scroll container so narrow
 * viewports never break the parent layout.
 *
 *   <DetailTable
 *     columns={[
 *       { key, label, align?, render?, bold?, muted?, nowrap?, width? }
 *     ]}
 *     rows={…}
 *   />
 */
export default function DetailTable({
    columns = [],
    rows = [],
    emptyMessage = "No details to show.",
    rowKey = (r, i) => r.id ?? i,
}) {
    if (!rows || rows.length === 0) {
        return (
            <div
                className="surface-panel"
                style={{
                    fontSize: "0.85rem",
                    color: "var(--text-tertiary)",
                    padding: "12px 14px",
                    textAlign: "center",
                }}
            >
                {emptyMessage}
            </div>
        );
    }

    return (
        <div className="detail-table-scroller">
            <table>
                <thead>
                    <tr>
                        {columns.map(c => (
                            <th
                                key={c.key}
                                style={{
                                    textAlign: c.align || "left",
                                    width: c.width,
                                }}
                            >
                                {c.label}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.map((row, i) => (
                        <tr key={rowKey(row, i)}>
                            {columns.map(c => (
                                <td
                                    key={c.key}
                                    style={{
                                        textAlign: c.align || "left",
                                        whiteSpace: c.nowrap ? "nowrap" : "normal",
                                        color: c.muted ? "var(--text-secondary)" : "var(--text-primary)",
                                        fontWeight: c.bold ? 600 : 400,
                                    }}
                                >
                                    {c.render ? c.render(row[c.key], row) : (row[c.key] ?? "—")}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
