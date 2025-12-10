import React, { useState } from 'react';
import api from '../api/axios';

const LedgerUpload = () => {
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [currentFile, setCurrentFile] = useState(null);

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

    const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
    const droppedFiles = Array.from(e.dataTransfer.files).filter(
      file => file.name.endsWith('.csv')
    );

    const validFiles = droppedFiles.filter(file => file.size <= MAX_FILE_SIZE);
    const oversizedFiles = droppedFiles.filter(file => file.size > MAX_FILE_SIZE);

    if (oversizedFiles.length > 0) {
      setError(`${oversizedFiles.length} file(s) exceed the 50MB size limit and were not added`);
    }

    if (validFiles.length > 0) {
      setFiles(validFiles);
      if (!oversizedFiles.length) {
        setError(null);
      }
      setResults([]);
    } else if (!oversizedFiles.length) {
      setError('Please drop CSV files only');
    }
  };

  const handleFileChange = (e) => {
    const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB
    const selectedFiles = Array.from(e.target.files);

    const validFiles = selectedFiles.filter(file => file.size <= MAX_FILE_SIZE);
    const oversizedFiles = selectedFiles.filter(file => file.size > MAX_FILE_SIZE);

    if (oversizedFiles.length > 0) {
      setError(`${oversizedFiles.length} file(s) exceed the 50MB size limit and were not added`);
    } else {
      setError(null);
    }

    setFiles(validFiles);
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
    setUploadProgress(0);

    try {
      // Upload all files in a single request for better performance
      const formData = new FormData();
      files.forEach(file => {
        formData.append('ledger', file);
      });

      setCurrentFile(`Uploading ${files.length} file(s)...`);

      const response = await api.post('/upload-ledger/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 300000, // 5 minutes timeout
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          setUploadProgress(percentCompleted);
        },
      });

      // Display results
      setResults([{
        success: true,
        message: response.data.message,
        licenses: response.data.licenses || [],
        stats: response.data.stats || {},
        failures: response.data.failures || []
      }]);

      // Clear files after successful upload
      setFiles([]);
      document.getElementById('file-input').value = '';
      setCurrentFile(null);
      setUploadProgress(0);

    } catch (err) {
      setError(
        err.response?.data?.error ||
        err.message ||
        'Failed to process files. Please try again or upload fewer files at once.'
      );
      setResults([]);
    } finally {
      setUploading(false);
      setCurrentFile(null);
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

              {/* Upload Progress */}
              {uploading && (
                <div className="mb-4">
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <small className="text-muted">{currentFile}</small>
                    <small className="text-muted">{uploadProgress}%</small>
                  </div>
                  <div className="progress" style={{ height: '8px' }}>
                    <div
                      className="progress-bar progress-bar-striped progress-bar-animated"
                      role="progressbar"
                      style={{ width: `${uploadProgress}%` }}
                      aria-valuenow={uploadProgress}
                      aria-valuemin="0"
                      aria-valuemax="100"
                    ></div>
                  </div>
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
              <div className="card-body p-3" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {results.map((result, index) => (
                  <div key={index}>
                    <div
                      className={`alert ${
                        result.success ? 'alert-success' : 'alert-danger'
                      } mb-3`}
                    >
                      <div className="d-flex align-items-start">
                        <i className={`bi ${
                          result.success ? 'bi-check-circle-fill' : 'bi-x-circle-fill'
                        } fs-4 me-3`}></i>
                        <div className="flex-grow-1">
                          {result.success ? (
                            <>
                              <p className="mb-2 fw-bold">{result.message}</p>

                              {result.stats && (
                                <div className="d-flex gap-3 mb-3">
                                  <small className="badge bg-primary">
                                    <i className="bi bi-file-earmark-check me-1"></i>
                                    Files: {result.stats.files_processed || 0}
                                  </small>
                                  <small className="badge bg-success">
                                    <i className="bi bi-card-list me-1"></i>
                                    Licenses: {result.stats.total_licenses || 0}
                                  </small>
                                  {result.stats.files_failed > 0 && (
                                    <small className="badge bg-danger">
                                      <i className="bi bi-exclamation-triangle me-1"></i>
                                      Failed: {result.stats.files_failed}
                                    </small>
                                  )}
                                </div>
                              )}

                              {result.failures && result.failures.length > 0 && (
                                <div className="alert alert-warning mb-2">
                                  <h6 className="alert-heading">
                                    <i className="bi bi-exclamation-triangle me-2"></i>
                                    Failed Files ({result.failures.length})
                                  </h6>
                                  {result.failures.map((failure, idx) => (
                                    <div key={idx} className="mb-1">
                                      <strong>{failure.file}:</strong> {failure.error}
                                    </div>
                                  ))}
                                </div>
                              )}

                              {result.licenses && result.licenses.length > 0 && (
                                <div>
                                  <small className="d-block mb-2 fw-bold">
                                    <i className="bi bi-card-checklist me-1"></i>
                                    License Numbers ({result.licenses.length}):
                                  </small>
                                  <div className="d-flex flex-wrap gap-1">
                                    {result.licenses.slice(0, 50).map((license, idx) => (
                                      <span key={idx} className="badge bg-success">
                                        {license}
                                      </span>
                                    ))}
                                    {result.licenses.length > 50 && (
                                      <span className="badge bg-secondary">
                                        +{result.licenses.length - 50} more
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
                  <li className="mb-1">Multiple files can be uploaded at once</li>
                  <li className="mb-1"><strong>Maximum file size: 50MB per file</strong></li>
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
