export default function Pagination({page, total, onChange}) {
    const pages = Array.from({length: total}, (_, i) => i + 1);

    return (
        <nav>
            <ul className="pagination">
                {pages.map((p) => (
                    <li key={p} className={`page-item ${p === page ? "active" : ""}`}>
                        <button className="page-link" onClick={() => onChange(p)}>
                            {p}
                        </button>
                    </li>
                ))}
            </ul>
        </nav>
    );
}
