import React from "react";

const MasterTable = ({
  schema = {},
  meta = {},
  records = [],
  loading = false,
  page = 1,
  pageCount = 1,
  setPage,
  onEdit,
  onDelete,
}) => {
  const hiddenFields = ["password", "secret", "token"];
  const fields =
    (meta.listDisplay && meta.listDisplay.length && meta.listDisplay) ||
    (meta.formFields && meta.formFields.length && meta.formFields.slice(0, 6)) ||
    Object.keys(schema || {}).filter((f) => !hiddenFields.includes(f));

  /** ✅ Pagination Controls */
  const renderPagination = () => {
    const pages = [];
    const start = Math.max(1, page - 2);
    const end = Math.min(pageCount, start + 4);
    for (let p = start; p <= end; p++) {
      pages.push(
        <button
          key={p}
          className={`btn btn-sm ${
            p === page ? "btn-primary" : "btn-outline-secondary"
          } mx-1`}
          onClick={() => setPage(p)}
        >
          {p}
        </button>
      );
    }
    return (
      <div className="d-flex justify-content-center mt-3">
        <button
          className="btn btn-sm btn-outline-secondary mx-1"
          disabled={page === 1}
          onClick={() => setPage(Math.max(1, page - 1))}
        >
          Prev
        </button>
        {pages}
        <button
          className="btn btn-sm btn-outline-secondary mx-1"
          disabled={page === pageCount}
          onClick={() => setPage(Math.min(pageCount, page + 1))}
        >
          Next
        </button>
      </div>
    );
  };

  /** ✅ Render cell data */
  const renderCell = (record, f) => {
    const val = record[f];
    if (Array.isArray(val)) return `${val.length} items`;
    if (val && typeof val === "object") {
      return (
        val.name ||
        val.hsn_code ||
        val.description ||
        val.code ||
        val.id ||
        JSON.stringify(val)
      );
    }
    if (
      typeof val === "string" &&
      val.match(/\.(jpg|jpeg|png|gif|svg|webp)(\?|$)/i)
    ) {
      return (
        <img
          src={val}
          alt={f}
          style={{ maxWidth: 80, maxHeight: 60, objectFit: "cover" }}
        />
      );
    }
    return val === null || val === undefined ? "" : String(val);
  };

  /** ✅ Render nested related arrays (formsets) as labeled tables */
  const renderNestedDetails = (record) => {
    const nestedKeys = Object.keys(record).filter(
      (k) => Array.isArray(record[k]) && record[k].length > 0
    );
    if (!nestedKeys.length) return null;

    return (
      <div className="mt-3">
        {nestedKeys.map((key) => (
          <div key={key} className="mt-2">
            <h6 className="fw-bold text-orange text-uppercase mb-2">
              {key.replace(/_/g, " ").replace("norm", "Norm")}
            </h6>
            <div className="table-responsive">
              <table className="table table-sm table-bordered mb-0">
                <thead>
                  <tr>
                    {Object.keys(record[key][0] || {}).map((col) => (
                      <th key={col} className="small text-secondary">
                        {col.replace(/_/g, " ")}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {record[key].map((row, i) => (
                    <tr key={i}>
                      {Object.keys(row).map((col) => (
                        <td key={col} className="small">
                          {typeof row[col] === "object"
                            ? row[col]?.name ||
                              row[col]?.description ||
                              row[col]?.code ||
                              row[col]?.id
                            : String(row[col] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))}
      </div>
    );
  };

  /** ✅ Main Table */
  return (
    <div className="table-responsive">
      <table className="table table-striped align-middle">
        <thead>
          <tr>
            {fields.map((f) => (
              <th key={f}>{schema[f]?.label || f}</th>
            ))}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={fields.length + 1} className="text-center">
                Loading...
              </td>
            </tr>
          ) : records.length ? (
            records.map((record) => (
              <React.Fragment key={record.id || JSON.stringify(record)}>
                <tr>
                  {fields.map((f) => (
                    <td key={f}>{renderCell(record, f)}</td>
                  ))}
                  <td>
                    <button
                      className="btn btn-sm btn-warning me-2"
                      onClick={() => onEdit(record)}
                    >
                      Edit
                    </button>
                    <button
                      className="btn btn-sm btn-danger"
                      onClick={() => onDelete(record.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                <tr>
                  <td colSpan={fields.length + 1}>{renderNestedDetails(record)}</td>
                </tr>
              </React.Fragment>
            ))
          ) : (
            <tr>
              <td colSpan={fields.length + 1} className="text-center">
                No records found.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {pageCount > 1 && renderPagination()}
    </div>
  );
};

export default MasterTable;
