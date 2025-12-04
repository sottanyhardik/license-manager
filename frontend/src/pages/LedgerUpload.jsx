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
    <div className="container-fluid p-4">
      {/* Page Header */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="mb-1">
            <i className="bi bi-file-earmark-spreadsheet me-2"></i>
            Ledger Upload
          </h4>
          <p className="text-muted mb-0">Upload DFIA license ledger files in CSV format</p>
        </div>
      </div>

      <div className="row g-3">
        {/* Main Upload Card */}
        <div className="col-lg-8">
          <div className="card">
            <div className="card-body p-4">
              {/* Drop Zone */}
              <div
                className={`border-2 border-dashed rounded p-5 text-center mb-4 ${
                  dragActive
                    ? 'border-primary bg-primary bg-opacity-10'
                    : 'border-secondary bg-light'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                style={{
                  cursor: 'pointer',
                  minHeight: '200px',
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'center',
                  transition: 'all 0.2s ease'
                }}
              >
                <div className="mb-3">
                  <i className={`bi bi-cloud-arrow-up display-1 ${
                    dragActive ? 'text-primary' : 'text-muted'
                  }`}></i>
                </div>
                <h5 className="mb-2">
                  {dragActive ? 'Drop files here' : 'Drag & drop your CSV files'}
                </h5>
                <p className="text-muted mb-3">or</p>
                <label htmlFor="file-input" className="btn btn-primary">
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
                <p className="text-muted mt-3 mb-0 small">
                  <i className="bi bi-info-circle me-1"></i>
                  Supported format: CSV files only
                </p>
              </div>

              {/* Selected Files List */}
              {files.length > 0 && (
                <div className="mb-4">
                  <div className="d-flex justify-content-between align-items-center mb-3">
                    <h6 className="mb-0">
                      <i className="bi bi-paperclip me-2"></i>
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
                  <div className="list-group">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="list-group-item d-flex justify-content-between align-items-center"
                      >
                        <div className="d-flex align-items-center">
                          <i className="bi bi-file-earmark-text text-success fs-4 me-3"></i>
                          <div>
                            <div className="fw-medium">{file.name}</div>
                            <small className="text-muted">{formatFileSize(file.size)}</small>
                          </div>
                        </div>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-danger"
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
                <div className="alert alert-danger d-flex align-items-center mb-4" role="alert">
                  <i className="bi bi-exclamation-triangle-fill me-2"></i>
                  <div>{error}</div>
                </div>
              )}

              {/* Upload Button */}
              <div className="d-grid">
                <button
                  className="btn btn-primary btn-lg"
                  onClick={handleUpload}
                  disabled={files.length === 0 || uploading}
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

          {/* Results Section */}
          {results.length > 0 && (
            <div className="card mt-3">
              <div className="card-header bg-white">
                <h6 className="mb-0">
                  <i className="bi bi-check-circle text-success me-2"></i>
                  Upload Results
                </h6>
              </div>
              <div className="card-body p-3" style={{ maxHeight: '400px', overflowY: 'auto' }}>
                {results.map((result, index) => (
                  <div
                    key={index}
                    className={`alert ${
                      result.success ? 'alert-success' : 'alert-danger'
                    } mb-3`}
                  >
                    <div className="d-flex align-items-start">
                      <i className={`bi ${
                        result.success ? 'bi-check-circle-fill' : 'bi-x-circle-fill'
                      } fs-4 me-3`}></i>
                      <div className="flex-grow-1">
                        <h6 className="alert-heading mb-2">{result.fileName}</h6>

                        {result.success ? (
                          <>
                            <p className="mb-2">{result.message}</p>

                            {result.stats && (
                              <div className="d-flex gap-3 mb-2">
                                <small>
                                  <strong>Licenses:</strong> {result.stats.total_licenses || 0}
                                </small>
                                <small>
                                  <strong>Processed:</strong> {result.stats.files_processed || 0}
                                </small>
                                {result.stats.files_failed > 0 && (
                                  <small>
                                    <strong>Failed:</strong> {result.stats.files_failed}
                                  </small>
                                )}
                              </div>
                            )}

                            {result.licenses && result.licenses.length > 0 && (
                              <div>
                                <small className="d-block mb-1">
                                  <strong>License Numbers:</strong>
                                </small>
                                <div className="d-flex flex-wrap gap-1">
                                  {result.licenses.slice(0, 8).map((license, idx) => (
                                    <span key={idx} className="badge bg-success">
                                      {license}
                                    </span>
                                  ))}
                                  {result.licenses.length > 8 && (
                                    <span className="badge bg-secondary">
                                      +{result.licenses.length - 8} more
                                    </span>
                                  )}
                                </div>
                              </div>
                            )}
                          </>
                        ) : (
                          <p className="mb-0">{result.error}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Instructions Sidebar */}
        <div className="col-lg-4">
          <div className="card">
            <div className="card-header bg-white">
              <h6 className="mb-0">
                <i className="bi bi-info-circle me-2"></i>
                File Format Guide
              </h6>
            </div>
            <div className="card-body">
              <h6 className="mb-3">Required CSV Columns:</h6>
              <div className="mb-3">
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
                <div className="d-flex align-items-center mb-2">
                  <i className="bi bi-check-circle-fill text-success me-2"></i>
                  <code>Lic.Date</code>
                </div>
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

              <div className="alert alert-info mb-0">
                <h6 className="alert-heading">
                  <i className="bi bi-lightbulb me-2"></i>
                  Important Notes
                </h6>
                <ul className="mb-0 small ps-3">
                  <li className="mb-1">CSV must include header row with exact column names</li>
                  <li className="mb-1">License numbers will be zero-padded to 10 digits</li>
                  <li className="mb-1">Date format: DD/MM/YYYY</li>
                  <li className="mb-1">Credit and Debit transactions are automatically processed</li>
                  <li>Multiple files can be uploaded at once</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LedgerUpload;
