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
      file => file.name.endsWith('.csv') || file.name.endsWith('.xlsx')
    );

    if (droppedFiles.length > 0) {
      setFiles(droppedFiles);
      setError(null);
    } else {
      setError('Please drop CSV or Excel files only');
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
      <div className="row mb-4">
        <div className="col-12">
          <div className="d-flex justify-content-between align-items-center">
            <div>
              <h4 className="mb-1">
                <i className="bi bi-file-earmark-spreadsheet me-2"></i>
                Ledger Upload
              </h4>
              <p className="text-muted mb-0">Upload DFIA license ledger files (CSV format)</p>
            </div>
          </div>
        </div>
      </div>

      {/* Upload Card */}
      <div className="row">
        <div className="col-12">
          <div className="card shadow-sm">
            <div className="card-body">
              {/* File Drop Zone */}
              <div
                className={`border-2 border-dashed rounded p-5 text-center mb-4 ${
                  dragActive ? 'border-primary bg-light' : 'border-secondary'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                style={{ cursor: 'pointer', transition: 'all 0.3s ease' }}
              >
                <i
                  className={`bi bi-cloud-upload display-4 mb-3 ${
                    dragActive ? 'text-primary' : 'text-muted'
                  }`}
                ></i>
                <h5 className="mb-2">Drag & Drop Files Here</h5>
                <p className="text-muted mb-3">or</p>
                <label htmlFor="file-input" className="btn btn-primary">
                  <i className="bi bi-folder2-open me-2"></i>
                  Browse Files
                </label>
                <input
                  id="file-input"
                  type="file"
                  accept=".csv,.xlsx"
                  multiple
                  onChange={handleFileChange}
                  className="d-none"
                />
                <p className="text-muted mt-3 mb-0 small">
                  Supported formats: CSV, Excel (.xlsx)
                </p>
              </div>

              {/* File List */}
              {files.length > 0 && (
                <div className="mb-4">
                  <h6 className="mb-3">
                    <i className="bi bi-files me-2"></i>
                    Selected Files ({files.length})
                  </h6>
                  <div className="list-group">
                    {files.map((file, index) => (
                      <div
                        key={index}
                        className="list-group-item d-flex justify-content-between align-items-center"
                      >
                        <div className="d-flex align-items-center">
                          <i className="bi bi-file-earmark-spreadsheet text-success fs-4 me-3"></i>
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
                          <i className="bi bi-trash"></i>
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
                      <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>
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
      </div>

      {/* Results Section */}
      {results.length > 0 && (
        <div className="row mt-4">
          <div className="col-12">
            <div className="card shadow-sm">
              <div className="card-header bg-white">
                <h5 className="mb-0">
                  <i className="bi bi-check-circle me-2"></i>
                  Upload Results
                </h5>
              </div>
              <div className="card-body">
                {results.map((result, index) => (
                  <div
                    key={index}
                    className={`alert ${
                      result.success ? 'alert-success' : 'alert-danger'
                    } mb-3`}
                  >
                    <div className="d-flex align-items-start">
                      <i
                        className={`bi ${
                          result.success ? 'bi-check-circle-fill' : 'bi-x-circle-fill'
                        } fs-4 me-3`}
                      ></i>
                      <div className="flex-grow-1">
                        <h6 className="alert-heading mb-2">
                          {result.fileName}
                        </h6>

                        {result.success ? (
                          <>
                            <p className="mb-2">{result.message}</p>

                            {result.stats && (
                              <div className="mb-2">
                                <small className="d-block">
                                  <strong>Statistics:</strong>
                                </small>
                                <small className="d-block">
                                  • Licenses Created: {result.stats.licenses_created || 0}
                                </small>
                                <small className="d-block">
                                  • Licenses Updated: {result.stats.licenses_updated || 0}
                                </small>
                                <small className="d-block">
                                  • Total Transactions: {result.stats.total_transactions || 0}
                                </small>
                              </div>
                            )}

                            {result.licenses && result.licenses.length > 0 && (
                              <div className="mt-2">
                                <small className="d-block mb-1">
                                  <strong>Processed Licenses:</strong>
                                </small>
                                <div className="d-flex flex-wrap gap-2">
                                  {result.licenses.map((license, idx) => (
                                    <span key={idx} className="badge bg-success">
                                      {license}
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </>
                        ) : (
                          <p className="mb-0 text-danger">{result.error}</p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Instructions Card */}
      <div className="row mt-4">
        <div className="col-12">
          <div className="card shadow-sm">
            <div className="card-header bg-white">
              <h5 className="mb-0">
                <i className="bi bi-info-circle me-2"></i>
                File Format Instructions
              </h5>
            </div>
            <div className="card-body">
              <h6 className="mb-3">Required CSV Format:</h6>
              <div className="table-responsive">
                <table className="table table-sm table-bordered">
                  <thead className="table-light">
                    <tr>
                      <th>Regn.No.</th>
                      <th>Regn.Date</th>
                      <th>Lic.No.</th>
                      <th>Lic.Date</th>
                      <th>RANo. (Port)</th>
                      <th>IEC</th>
                      <th>Scheme Code</th>
                      <th>Notification</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>3011006401</td>
                      <td>24/01/2025</td>
                      <td>3011006401</td>
                      <td>24/01/2025</td>
                      <td>INMUN1</td>
                      <td>1059704957</td>
                      <td>26</td>
                      <td>0325/2023</td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <div className="alert alert-info mt-3">
                <h6 className="alert-heading">
                  <i className="bi bi-lightbulb me-2"></i>
                  Important Notes:
                </h6>
                <ul className="mb-0">
                  <li>The CSV file must contain header row with exact column names</li>
                  <li>License numbers and IEC codes will be zero-padded to 10 digits</li>
                  <li>Dates should be in DD/MM/YYYY format</li>
                  <li>Credit transactions (license imports) and Debit transactions (BOE) are automatically processed</li>
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
