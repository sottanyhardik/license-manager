import React, { useState } from "react";
import { Button } from "react-bootstrap";

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
  const [expandedRows, setExpandedRows] = useState(new Set());

  const hiddenFields = ["password", "secret", "token"];
  const fields =
    (meta.listDisplay && meta.listDisplay.length && meta.listDisplay) ||
    (meta.formFields && meta.formFields.length && meta.formFields.slice(0, 6)) ||
    Object.keys(schema || {}).filter((f) => !hiddenFields.includes(f));

  /** ✅ Toggle expand/collapse using Bootstrap */
  const toggleExpand = (id) => {
    setExpandedRows((prev) => {
      const newSet = new Set(prev);
      newSet.has(id) ? newSet.delete(id) : newSet.add(id);
      return newSet;
    });
  };

  /** ✅ Pagination Controls */
  const renderPagination = () => {
    const pages = [];
    const start = Math.max(1, page - 2);
    const end = Math.min(pageCount, start + 4);
    for (let p = start; p <= end; p++) {
      pages.push(
        <Button
          key={p}
          size="sm"
          variant={p === page ? "primary" : "outline-secondary"}
          className="mx-1"
          onClick={() => setPage(p)}
        >
          {p}
        </Button>
      );
    }
    return (
      <div className="d-flex justify-content-center mt-3">
        <Button
          size="sm"
          variant="outline-secondary"
          className="mx-1"
          disabled={page === 1}
          onClick={() => setPage(Math.max(1, page - 1))}
        >
          Prev
        </Button>
        {pages}
        <Button
          size="sm"
          variant="outline-secondary"
          className="mx-1"
          disabled={page === pageCount}
          onClick={() => setPage(Math.min(pageCount, page + 1))}
        >
          Next
        </Button>
      </div>
    );
  };

  /** ✅ Cell renderer with smart formatting */
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
          className="img-thumbnail"
        />
      );
    }
    return val === null || val === undefined ? "" : String(val);
  };

  /** ✅ Nested (Bootstrap Collapse) */
  const renderNestedDetails = (record, index) => {
    const nestedKeys = Object.keys(record).filter(
      (k) => Array.isArray(record[k]) && record[k].length > 0
    );
    if (!nestedKeys.length) return null;

    return (
      <div
        className={`accordion collapse ${
          expandedRows.has(record.id) ? "show" : ""
        }`}
        id={`collapse-${record.id}`}
      >
        {nestedKeys.map((key) => (
          <div key={key} className="card mt-2 shadow-sm border-0">
            <div className="card-header bg-light">
              <h6 className="fw-bold text-orange text-uppercase mb-0">
                {key
                  .replace(/_/g, " ")
                  .replace("norm", "Norm")
                  .replace("export", "Export Norms")
                  .replace("import", "Import Norms")}
              </h6>
            </div>
            <div className="card-body p-2">
              <div className="table-responsive">
                <table className="table table-sm table-bordered mb-0">
                  <thead className="table-secondary">
                    <tr>
                      {Object.keys(record[key][0] || {})
                        .filter(
                          (col) =>
                            ![
                              "id",
                              "created_on",
                              "modified_on",
                              "created_by",
                              "modified_by",
                            ].includes(col)
                        )
                        .map((col) => (
                          <th key={col} className="small text-capitalize">
                            {col.replace(/_/g, " ")}
                          </th>
                        ))}
                    </tr>
                  </thead>
                  <tbody>
                    {record[key].map((row, i) => (
                      <tr key={i}>
                        {Object.keys(row)
                          .filter(
                            (col) =>
                              ![
                                "id",
                                "created_on",
                                "modified_on",
                                "created_by",
                                "modified_by",
                              ].includes(col)
                          )
                          .map((col) => (
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
          </div>
        ))}
      </div>
    );
  };

  /** ✅ Main Table */
  return (
    <div className="table-responsive">
      <table className="table table-striped align-middle">
        <thead className="table-light">
          <tr>
            <th style={{ width: "40px" }}></th>
            {fields.map((f) => (
              <th key={f}>{schema[f]?.label || f}</th>
            ))}
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={fields.length + 2} className="text-center">
                Loading...
              </td>
            </tr>
          ) : records.length ? (
            records.map((record, index) => (
              <React.Fragment key={record.id || JSON.stringify(record)}>
                <tr>
                  <td className="text-center">
                    <Button
                      size="sm"
                      variant="outline-secondary"
                      data-bs-toggle="collapse"
                      data-bs-target={`#collapse-${record.id}`}
                      aria-expanded={expandedRows.has(record.id)}
                      aria-controls={`collapse-${record.id}`}
                      onClick={() => toggleExpand(record.id)}
                    >
                      {expandedRows.has(record.id) ? (
                        <i className="bi bi-dash-lg"></i>
                      ) : (
                        <i className="bi bi-plus-lg"></i>
                      )}
                    </Button>
                  </td>
                  {fields.map((f) => (
                    <td key={f}>{renderCell(record, f)}</td>
                  ))}
                  <td>
                    <Button
                      size="sm"
                      variant="warning"
                      className="me-2"
                      onClick={() => onEdit(record)}
                    >
                      <i className="bi bi-pencil-square"></i>
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => onDelete(record.id)}
                    >
                      <i className="bi bi-trash"></i>
                    </Button>
                  </td>
                </tr>
                {expandedRows.has(record.id) && (
                  <tr>
                    <td colSpan={fields.length + 2}>
                      {renderNestedDetails(record, index)}
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))
          ) : (
            <tr>
              <td colSpan={fields.length + 2} className="text-center">
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
