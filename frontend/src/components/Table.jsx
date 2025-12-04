export default function Table({columns, data}) {
    return (
        <table className="table table-striped table-hover">
            <thead>
            <tr>
                {columns.map((c) => (
                    <th key={c.key}>{c.label}</th>
                ))}
            </tr>
            </thead>
            <tbody>
            {data.map((row) => (
                <tr key={row.id}>
                    {columns.map((c) => (
                        <td key={c.key}>{row[c.key]}</td>
                    ))}
                </tr>
            ))}
            </tbody>
        </table>
    );
}
