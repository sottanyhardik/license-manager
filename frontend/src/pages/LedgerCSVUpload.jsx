import React, { useState } from 'react';
import api from '../api/axios';
import { useFileUpload } from '../hooks';

const LedgerCSVUpload = () => {
  const [showTemplate, setShowTemplate] = useState(false);
  const [templateInfo, setTemplateInfo] = useState(null);

  const {
    files,
    uploading,
    results,
    error,
    handleFileChange,
    handleUpload,
    removeFile,
  } = useFileUpload({
    endpoint: 'ledger-csv-upload/',
    fileFieldName: 'file',
    multiple: false,
    accept: '.csv',
    onSuccess: (results) => {
      const fileInput = document.getElementById('csv-file-input');
      if (fileInput && results.some(r => r.success)) fileInput.value = '';
    },
  });

  const file = files?.length > 0 ? files[0] : null;
  const result = results?.length > 0 ? results[0] : null;

  const fetchTemplateInfo = async () => {
    try {
      const response = await api.get('ledger-csv-upload/');
      setTemplateInfo(response.data);
      setShowTemplate(true);
    } catch {}
  };

  const downloadTemplate = () => {
    const headers = ['DFIA', 'sr_no', 'BENO', 'BEDT', 'PORT', 'CIFINR', 'CIFD', 'QTY'];
    const exampleRow = ['0311031558', '1', '1234567', '01/01/2024', 'INMUN1', '10000.50', '1500.25', '1000'];
    const blob = new Blob([[headers.join(','), exampleRow.join(',')].join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'ledger_template.csv'; a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
      {/* Header */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
            <i className="bi bi-file-earmark-arrow-up me-2" style={{ color: '#4F46E5' }}></i>
            Custom Ledger CSV Upload
          </h4>
          <small className="text-muted">Import DFIA debit transactions from CSV file</small>
        </div>
        <button
          className="btn btn-sm btn-outline-primary"
          onClick={fetchTemplateInfo}
        >
          <i className="bi bi-info-circle me-1"></i>View Instructions
        </button>
      </div>

      {/* Instructions panel */}
      {showTemplate && templateInfo && (
        <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px', borderLeft: '3px solid #4F46E5' }}>
          <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
            <h6 className="mb-0 fw-semibold">
              <i className="bi bi-file-text me-2" style={{ color: '#4F46E5' }}></i>
              CSV Format Instructions
            </h6>
            <button className="btn-close" onClick={() => setShowTemplate(false)}></button>
          </div>
          <div className="card-body p-4">
            <div className="row g-3">
              <div className="col-md-4">
                <div style={{ background: 'var(--bs-gray-50)', borderRadius: '8px', padding: '12px' }}>
                  <div className="fw-semibold small mb-2 text-muted">Required Headers</div>
                  <code style={{ fontSize: '0.8rem', wordBreak: 'break-all' }}>
                    {templateInfo.required_headers?.join(', ')}
                  </code>
                </div>
              </div>
              <div className="col-md-4">
                <div style={{ background: 'var(--bs-gray-50)', borderRadius: '8px', padding: '12px' }}>
                  <div className="fw-semibold small mb-2 text-muted">Column Descriptions</div>
                  {Object.entries(templateInfo.header_descriptions || {}).map(([key, value]) => (
                    <div key={key} className="small mb-1">
                      <code className="fw-bold">{key}:</code> <span className="text-muted">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div className="col-md-4">
                <div style={{ background: '#fef3c7', borderRadius: '8px', padding: '12px' }}>
                  <div className="fw-semibold small mb-2" style={{ color: '#92400e' }}>Notes</div>
                  <ul className="mb-0 ps-3">
                    {(templateInfo.notes || []).map((note, idx) => (
                      <li key={idx} className="small text-muted">{note}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
            <div className="mt-3">
              <button
                className="btn btn-sm btn-primary"
                onClick={downloadTemplate}
                style={{ background: 'linear-gradient(135deg,#4F46E5,#4338CA)', border: 'none' }}
              >
                <i className="bi bi-download me-1"></i>Download Template CSV
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Upload card */}
      <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
        <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
          <h6 className="mb-0 fw-semibold">
            <i className="bi bi-cloud-upload me-2" style={{ color: '#4F46E5' }}></i>
            Upload File
          </h6>
        </div>
        <div className="card-body p-4">
          {/* Drop zone */}
          <label
            htmlFor="csv-file-input"
            style={{
              display: 'block', border: '2px dashed #d1d5db', borderRadius: '12px',
              padding: '40px 24px', textAlign: 'center', cursor: 'pointer',
              transition: 'border-color 0.15s', background: file ? '#f0fdf4' : 'white'
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = '#4F46E5'}
            onMouseLeave={e => e.currentTarget.style.borderColor = file ? '#10b981' : '#d1d5db'}
          >
            <i className="bi bi-file-earmark-arrow-up d-block mb-2" style={{ fontSize: '2.5rem', color: file ? '#10b981' : '#9ca3af' }}></i>
            {file ? (
              <>
                <p className="fw-semibold mb-1 text-success">{file.name}</p>
                <small className="text-muted">{(file.size / 1024).toFixed(1)} KB — click to replace</small>
              </>
            ) : (
              <>
                <p className="fw-semibold mb-1">Click to upload <span className="text-muted fw-normal">or drag and drop</span></p>
                <small className="text-muted">CSV files only</small>
              </>
            )}
            <input id="csv-file-input" type="file" accept=".csv" onChange={handleFileChange} className="d-none" />
          </label>

          {file && (
            <div className="d-flex align-items-center gap-2 mt-3 p-3" style={{ background: 'var(--bs-gray-50)', borderRadius: '8px' }}>
              <i className="bi bi-file-earmark-text text-success" style={{ fontSize: '1.25rem', flexShrink: 0 }}></i>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="fw-medium small text-truncate">{file.name}</div>
                <small className="text-muted">{(file.size / 1024).toFixed(1)} KB</small>
              </div>
              <button
                className="btn btn-sm btn-outline-danger"
                onClick={() => { removeFile(0); document.getElementById('csv-file-input').value = ''; }}
              >
                <i className="bi bi-trash"></i>
              </button>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className="btn btn-primary w-100 mt-3"
            style={{
              padding: '12px', fontWeight: '600', borderRadius: '10px',
              background: !file || uploading ? undefined : 'linear-gradient(135deg,#4F46E5,#4338CA)',
              border: 'none'
            }}
          >
            {uploading ? (
              <><span className="spinner-border spinner-border-sm me-2"></span>Processing...</>
            ) : (
              <><i className="bi bi-cloud-upload me-2"></i>Upload and Process</>
            )}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="alert alert-danger d-flex align-items-start gap-2 mt-4">
          <i className="bi bi-exclamation-circle-fill flex-shrink-0 mt-1"></i>
          <div><strong>Error</strong><div className="small mt-1">{error}</div></div>
        </div>
      )}

      {/* Success result */}
      {result?.success && (
        <div className="card border-0 shadow-sm mt-4" style={{ borderRadius: '12px', borderLeft: '3px solid #10b981' }}>
          <div className="card-body p-4">
            <div className="d-flex align-items-center gap-2 mb-3">
              <i className="bi bi-check-circle-fill text-success" style={{ fontSize: '1.25rem' }}></i>
              <h6 className="mb-0 fw-bold text-success">{result.message || result.data?.message || 'Upload Successful'}</h6>
            </div>
            {result.data && (
              <div className="d-flex gap-3 flex-wrap mb-3">
                <span className="badge bg-success fs-6 px-3 py-2">
                  <i className="bi bi-check me-1"></i>{result.data.success_count} processed
                </span>
                {result.data.error_count > 0 && (
                  <span className="badge bg-danger fs-6 px-3 py-2">
                    <i className="bi bi-x me-1"></i>{result.data.error_count} errors
                  </span>
                )}
                {result.data.warning_count > 0 && (
                  <span className="badge bg-warning text-dark fs-6 px-3 py-2">
                    <i className="bi bi-exclamation me-1"></i>{result.data.warning_count} warnings
                  </span>
                )}
              </div>
            )}
            {result.data?.errors?.length > 0 && (
              <>
                <div className="fw-semibold small text-danger mb-2">
                  <i className="bi bi-exclamation-triangle me-1"></i>Row Errors
                </div>
                <div style={{ maxHeight: 200, overflowY: 'auto', borderRadius: 8, border: '1px solid #fecaca', background: '#fff5f5' }}>
                  {result.data.errors.map((err, idx) => (
                    <div key={idx} className="small px-3 py-2" style={{ borderBottom: idx < result.data.errors.length - 1 ? '1px solid #fecaca' : 'none' }}>
                      <strong>Row {err.row}:</strong> <span className="text-danger">{err.error}</span>
                    </div>
                  ))}
                </div>
                {result.data.note && <small className="text-muted mt-2 d-block">{result.data.note}</small>}
              </>
            )}
          </div>
        </div>
      )}

      {/* Error result */}
      {result && !result.success && (
        <div className="alert alert-danger d-flex align-items-start gap-2 mt-4">
          <i className="bi bi-exclamation-circle-fill flex-shrink-0 mt-1"></i>
          <div><strong>Upload Failed</strong><div className="small mt-1">{result.error}</div></div>
        </div>
      )}
    </div>
  );
};

export default LedgerCSVUpload;
