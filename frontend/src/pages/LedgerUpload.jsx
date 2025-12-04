import React, { useState } from 'react';
import api from '../api/axios';

const LedgerUpload = () => {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      file => file.name.endsWith('.csv')
    );

    if (droppedFiles.length > 0) {
      setFiles(droppedFiles);
      setError(null);
      setResults([]);
    } else {
      setError('Please drop CSV files only');
    }
  };

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files);
    setFiles(selectedFiles);
    setError(null);
    setResults([]);
  };

  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) {
      setError('Please select at least one file');
      return;
    }

    setUploading(true);
    setError(null);
    const uploadResults = [];

    try {
      for (const file of files) {
        const formData = new FormData();
        formData.append('ledger', file);

        try {
          const response = await api.post('/licenses/upload-ledger/', formData, {
            headers: {
              'Content-Type': 'multipart/form-data',
            },
          });

          uploadResults.push({
            fileName: file.name,
            success: true,
            message: response.data.message || 'File processed successfully',
            licenses: response.data.licenses || [],
            stats: response.data.stats || {}
          });
        } catch (err) {
          uploadResults.push({
            fileName: file.name,
            success: false,
            error: err.response?.data?.error || err.message || 'Failed to process file'
          });
        }
      }

      setResults(uploadResults);

      // Clear files after successful upload
      const hasSuccess = uploadResults.some(r => r.success);
      if (hasSuccess) {
        setFiles([]);
        document.getElementById('file-input').value = '';
      }
    } catch (err) {
      setError('An unexpected error occurred during upload');
    } finally {
      setUploading(false);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
  };

  return (
    <div className="container-fluid px-4 py-3">
      {/* Header */}
      <div className="row mb-4">
        <div className="col-12">
          <div className="d-flex align-items-center mb-2">
            <div className="bg-primary bg-opacity-10 rounded p-2 me-3">
              <i className="bi bi-file-earmark-spreadsheet text-primary fs-3"></i>
            </div>
            <div>
              <h4 className="mb-0 fw-bold">Ledger Upload</h4>
              <p className="text-muted mb-0 small">Upload DFIA license ledger files in CSV format</p>
            </div>
          </div>
        </div>
      </div>

      <div className="row g-4">
        {/* Left Column - Upload Section */}
        <div className="col-lg-7">
          <div className="card border-0 shadow-sm h-100">
            <div className="card-body p-4">
              {/* Drop Zone */}
              <div
                className={`border-2 border-dashed rounded-3 p-5 text-center transition-all ${
                  dragActive
                    ? 'border-primary bg-primary bg-opacity-10'
                    : 'border-light bg-light bg-opacity-50'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                style={{
                  cursor: 'pointer',
                  minHeight: '240px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  transition: 'all 0.3s ease'
                }}
              >
                <div className="mb-3">
                  <i className={`bi bi-cloud-arrow-up display-1 ${
                    dragActive ? 'text-primary' : 'text-muted'
                  }`}></i>
                </div>
                <h5 className="fw-semibold mb-2">
                  {dragActive ? 'Drop files here' : 'Drag & drop your files'}
                </h5>
                <p className="text-muted mb-3 small">or</p>
                <label htmlFor="file-input" className="btn btn-primary px-4">
                  <i className="bi bi-folder2-open me-2"></i>
                  Browse Files
                </label>
                <input
                  id="file-input"
                  type="file"
                  accept=".csv"
                  multiple
                  onChange={handleFileChange}
                  className="d-none"
                />
                <p className="text-muted mt-3 mb-0" style={{ fontSize: '0.85rem' }}>
                  <i className="bi bi-info-circle me-1"></i>
                  Supported format: CSV files only
                </p>
              </div>

              {/* Selected Files */}
              {files.length > 0 && (
                <div className="mt-4">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h6 className="mb-0 fw-semibold">
                      <i className="bi bi-paperclip me-2 text-primary"></i>
                      Selected Files ({files.length})
                    </h6>
                    <button
                      className="btn btn-sm btn-outline-danger"
                      onClick={() => {
                        setFiles([]);
                        document.getElementById('file-input').value = '';
                      }}
                      disabled={uploading}
                    >
                      <i className="bi bi-trash me-1"></i>
                      Clear All
                    </button>
                  </div>
                  <div className="list-group list-group-flush">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="list-group-item px-0 d-flex justify-content-between align-items-center"
                      >
                        <div className="d-flex align-items-center">
                          <div className="bg-success bg-opacity-10 rounded p-2 me-3">
                            <i className="bi bi-file-earmark-text text-success fs-5"></i>
                          </div>
                          <div>
                            <div className="fw-medium mb-0">{file.name}</div>
                            <small className="text-muted">{formatFileSize(file.size)}</small>
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn btn-sm btn-light text-danger"
                          onClick={() => removeFile(index)}
                          disabled={uploading}
                        >
                          <i className="bi bi-x-lg"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error Alert */}
              {error && (
                <div className="alert alert-danger d-flex align-items-center mt-4 mb-0" role="alert">
                  <i className="bi bi-exclamation-triangle-fill me-2 fs-5"></i>
                  <div>{error}</div>
                </div>
              )}

              {/* Upload Button */}
              <div className="d-grid mt-4">
                <button
                  className="btn btn-primary btn-lg py-3"
                  onClick={handleUpload}
                  disabled={files.length === 0 || uploading}
                  style={{ fontSize: '1rem', fontWeight: '600' }}
                >
                  {uploading ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                      Processing {files.length} file{files.length > 1 ? 's' : ''}...
                    </>
                  ) : (
                    <>
                      <i className="bi bi-upload me-2"></i>
                      Upload & Process
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Instructions & Results */}
        <div className="col-lg-5">
          {/* Results Section */}
          {results.length > 0 ? (
            <div className="card border-0 shadow-sm mb-4">
              <div className="card-header bg-white border-bottom py-3">
                <h6 className="mb-0 fw-semibold">
                  <i className="bi bi-check-circle text-success me-2"></i>
                  Upload Results
                </h6>
              </div>
              <div className="card-body p-3" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {results.map((result, index) => (
                  <div
                    key={index}
                    className={`border rounded-3 p-3 mb-3 ${
                      result.success
                        ? 'border-success bg-success bg-opacity-10'
                        : 'border-danger bg-danger bg-opacity-10'
                    }`}
                  >
                    <div className="d-flex align-items-start">
                      <div className={`rounded-circle p-2 me-3 ${
                        result.success ? 'bg-success' : 'bg-danger'
                      }`} style={{ width: '40px', height: '40px' }}>
                        <i className={`bi ${
                          result.success ? 'bi-check-lg' : 'bi-x-lg'
                        } text-white d-flex justify-content-center align-items-center fs-5`}></i>
                      </div>
                      <div className="flex-grow-1">
                        <h6 className="mb-2 fw-semibold" style={{ fontSize: '0.9rem' }}>
                          {result.fileName}
                        </h6>

                        {result.success ? (
                          <>
                            <p className="mb-2 text-success small">{result.message}</p>

                            {result.stats && (
                              <div className="bg-white rounded p-2 mb-2">
                                <div className="row g-2 text-center">
                                  <div className="col-4">
                                    <div className="fw-bold text-primary">{result.stats.total_licenses || 0}</div>
                                    <div className="text-muted" style={{ fontSize: '0.75rem' }}>Licenses</div>
                                  </div>
                                  <div className="col-4">
                                    <div className="fw-bold text-success">{result.stats.files_processed || 0}</div>
                                    <div className="text-muted" style={{ fontSize: '0.75rem' }}>Processed</div>
                                  </div>
                                  <div className="col-4">
                                    <div className="fw-bold text-danger">{result.stats.files_failed || 0}</div>
                                    <div className="text-muted" style={{ fontSize: '0.75rem' }}>Failed</div>
                                  </div>
                                </div>
                              </div>
                            )}

                            {result.licenses && result.licenses.length > 0 && (
                              <div>
                                <small className="text-muted d-block mb-2">License Numbers:</small>
                                <div className="d-flex flex-wrap gap-1">
                                  {result.licenses.slice(0, 5).map((license, idx) => (
                                    <span key={idx} className="badge bg-primary" style={{ fontSize: '0.75rem' }}>
                                      {license}
                                    </span>
                                  ))}
                                  {result.licenses.length > 5 && (
                                    <span className="badge bg-secondary" style={{ fontSize: '0.75rem' }}>
                                      +{result.licenses.length - 5} more
                                    </span>
                                  )}
                                </div>
                              </div>
                            )}
                          </>
                        ) : (
                          <p className="mb-0 text-danger small">{result.error}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            /* Instructions Card */
            <div className="card border-0 shadow-sm">
              <div className="card-header bg-white border-bottom py-3">
                <h6 className="mb-0 fw-semibold">
                  <i className="bi bi-info-circle text-primary me-2"></i>
                  File Format Guide
                </h6>
              </div>
              <div className="card-body p-4">
                <div className="mb-4">
                  <h6 className="fw-semibold mb-3" style={{ fontSize: '0.9rem' }}>Required CSV Columns:</h6>
                  <div className="bg-light rounded-3 p-3">
                    <div className="row g-2 small">
                      <div className="col-6">
                        <div className="d-flex align-items-center mb-2">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>Regn.No.</code>
                        </div>
                        <div className="d-flex align-items-center mb-2">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>Regn.Date</code>
                        </div>
                        <div className="d-flex align-items-center mb-2">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>Lic.No.</code>
                        </div>
                        <div className="d-flex align-items-center">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>Lic.Date</code>
                        </div>
                      </div>
                      <div className="col-6">
                        <div className="d-flex align-items-center mb-2">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>IEC</code>
                        </div>
                        <div className="d-flex align-items-center mb-2">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>Scheme.Cd.</code>
                        </div>
                        <div className="d-flex align-items-center mb-2">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>Port</code>
                        </div>
                        <div className="d-flex align-items-center">
                          <i className="bi bi-check-circle-fill text-success me-2"></i>
                          <code>Notification</code>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                <div className="alert alert-info mb-0" style={{ fontSize: '0.85rem' }}>
                  <h6 className="alert-heading fw-semibold" style={{ fontSize: '0.9rem' }}>
                    <i className="bi bi-lightbulb me-2"></i>
                    Important Notes
                  </h6>
                  <ul className="mb-0 ps-3">
                    <li className="mb-1">CSV must include header row with exact column names</li>
                    <li className="mb-1">License numbers auto-padded to 10 digits</li>
                    <li className="mb-1">Date format: <code>DD/MM/YYYY</code></li>
                    <li className="mb-1">Credit (imports) and Debit (BOE) auto-processed</li>
                    <li>Multiple files can be uploaded simultaneously</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default LedgerUpload;
