import React, { useState, useEffect } from 'react';
import { useFileUpload } from '../hooks';
import axios from 'axios';

const LedgerUpload = () => {
  const [asyncTasks, setAsyncTasks] = useState([]);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [useAsyncMode, setUseAsyncMode] = useState(true);

  const {
    files,
    uploading,
    results,
    error,
    dragActive,
    fileProgress,
    handleDrag,
    handleDrop,
    handleFileChange,
    handleUpload: originalHandleUpload,
    formatFileSize,
    removeFile,
    clearFiles,
  } = useFileUpload({
    endpoint: '/upload-ledger/',
    fileFieldName: 'ledger',
    uploadMode: 'sequential',
    multiple: true,
    accept: '.csv',
    maxFileSize: 50 * 1024 * 1024, // 50MB
    timeout: 300000,
    onSuccess: (results) => {
      const fileInput = document.getElementById('file-input');
      if (fileInput && results.some(r => r.success)) {
        fileInput.value = '';
      }
    },
  });

  // Handle async upload with task tracking
  const handleAsyncUpload = async () => {
    if (files.length === 0) return;

    const formData = new FormData();
    files.forEach((file) => {
      formData.append('ledger', file);
    });
    formData.append('async', 'true');

    try {
      const response = await axios.post('/api/upload-ledger/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.tasks) {
        setAsyncTasks(response.data.tasks);
        setShowTaskModal(true);
        clearFiles();
        document.getElementById('file-input').value = '';
      }
    } catch (err) {
      console.error('Upload error:', err);
    }
  };

  const handleUpload = () => {
    if (useAsyncMode) {
      handleAsyncUpload();
    } else {
      originalHandleUpload();
    }
  };

  // Task Status Modal Component
  const TaskStatusModal = ({ tasks, show, onHide }) => {
    const [taskStatuses, setTaskStatuses] = useState({});

    useEffect(() => {
      if (!show || tasks.length === 0) return;

      const intervals = tasks.map((task) => {
        return setInterval(async () => {
          try {
            const response = await axios.get(`/api/ledger-task-status/${task.task_id}/`);
            setTaskStatuses((prev) => ({
              ...prev,
              [task.task_id]: response.data,
            }));

            // Stop polling if task is complete
            if (response.data.state === 'SUCCESS' || response.data.state === 'FAILURE') {
              clearInterval(intervals.find(i => i === interval));
            }
          } catch (err) {
            console.error('Error fetching task status:', err);
          }
        }, 2000); // Poll every 2 seconds
      });

      return () => {
        intervals.forEach(clearInterval);
      };
    }, [tasks, show]);

    if (!show) return null;

    return (
      <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
        <div className="modal-dialog modal-lg modal-dialog-scrollable">
          <div className="modal-content">
            <div className="modal-header">
              <h5 className="modal-title">
                <i className="bi bi-gear-fill me-2 spinner-border spinner-border-sm"></i>
                Processing Ledger Files
              </h5>
              <button type="button" className="btn-close" onClick={onHide}></button>
            </div>
            <div className="modal-body">
              {tasks.map((task) => {
                const status = taskStatuses[task.task_id];
                const isComplete = status?.state === 'SUCCESS';
                const isFailed = status?.state === 'FAILURE';
                const isProgress = status?.state === 'PROGRESS';

                return (
                  <div key={task.task_id} className="card mb-3">
                    <div className="card-body">
                      <div className="d-flex justify-content-between align-items-start mb-3">
                        <div>
                          <h6 className="mb-1">
                            <i className="bi bi-file-earmark-text me-2"></i>
                            {task.file}
                          </h6>
                          <small className="text-muted">Task ID: {task.task_id}</small>
                        </div>
                        <span className={`badge ${
                          isComplete ? 'bg-success' :
                          isFailed ? 'bg-danger' :
                          'bg-primary'
                        }`}>
                          {status?.state || 'QUEUED'}
                        </span>
                      </div>

                      {isProgress && status && (
                        <>
                          <div className="progress mb-2" style={{ height: '20px' }}>
                            <div
                              className="progress-bar progress-bar-striped progress-bar-animated"
                              style={{
                                width: `${(status.current / status.total) * 100}%`
                              }}
                            >
                              {status.current} / {status.total}
                            </div>
                          </div>
                          <p className="mb-2 small text-muted">{status.status}</p>

                          {status.processed_licenses?.length > 0 && (
                            <div className="mb-2">
                              <small className="fw-bold">Processed Licenses ({status.processed_licenses.length}):</small>
                              <div className="d-flex flex-wrap gap-1 mt-1">
                                {status.processed_licenses.slice(-5).map((license, idx) => (
                                  <span key={idx} className="badge bg-success bg-opacity-75">
                                    {license}
                                  </span>
                                ))}
                                {status.processed_licenses.length > 5 && (
                                  <span className="badge bg-secondary">
                                    +{status.processed_licenses.length - 5} more
                                  </span>
                                )}
                              </div>
                            </div>
                          )}

                          {status.failed_licenses?.length > 0 && (
                            <div className="alert alert-danger alert-sm mb-0">
                              <small className="fw-bold">Failed: {status.failed_licenses.length}</small>
                            </div>
                          )}
                        </>
                      )}

                      {isComplete && status?.result && (
                        <div className="alert alert-success mb-0">
                          <div className="d-flex justify-content-between align-items-center">
                            <div>
                              <i className="bi bi-check-circle-fill me-2"></i>
                              <strong>Completed Successfully</strong>
                            </div>
                            <span className="badge bg-success">
                              {status.result.processed_count} licenses
                            </span>
                          </div>
                          {status.result.failed_count > 0 && (
                            <div className="mt-2 text-warning">
                              <i className="bi bi-exclamation-triangle me-1"></i>
                              {status.result.failed_count} license(s) failed
                            </div>
                          )}
                        </div>
                      )}

                      {isFailed && status && (
                        <div className="alert alert-danger mb-0">
                          <i className="bi bi-x-circle-fill me-2"></i>
                          <strong>Failed:</strong> {status.error}
                        </div>
                      )}

                      {!status && (
                        <div className="text-muted">
                          <i className="bi bi-hourglass-split me-2"></i>
                          Waiting to start...
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={onHide}>
                Close
              </button>
            </div>
          </div>
        </div>
      </div>
    );
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
        <div className="form-check form-switch">
          <input
            className="form-check-input"
            type="checkbox"
            id="asyncModeSwitch"
            checked={useAsyncMode}
            onChange={(e) => setUseAsyncMode(e.target.checked)}
          />
          <label className="form-check-label" htmlFor="asyncModeSwitch">
            <i className="bi bi-lightning-charge-fill me-1"></i>
            Async Mode {useAsyncMode ? '(No Timeout)' : '(May Timeout)'}
          </label>
        </div>
      </div>

      {/* Task Status Modal */}
      <TaskStatusModal
        tasks={asyncTasks}
        show={showTaskModal}
        onHide={() => setShowTaskModal(false)}
      />

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
                        clearFiles();
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
              {uploading && Object.keys(fileProgress).length > 0 && (
                <div className="mb-4">
                  <div className="mb-3">
                    <h6 className="mb-2">
                      <i className="bi bi-cloud-upload me-2"></i>
                      Uploading Files
                    </h6>
                  </div>
                  {Object.entries(fileProgress).map(([index, fileData]) => (
                    <div key={index} className="mb-3">
                      <div className="d-flex justify-content-between align-items-center mb-1">
                        <small className="text-truncate me-2" style={{ maxWidth: '70%' }}>
                          <i className={`bi ${
                            fileData.status === 'completed' ? 'bi-check-circle-fill text-success' :
                            fileData.status === 'failed' ? 'bi-x-circle-fill text-danger' :
                            'bi-hourglass-split text-primary'
                          } me-1`}></i>
                          {fileData.name}
                        </small>
                        <small className="text-muted">
                          {fileData.status === 'completed' ? '✓ Done' :
                           fileData.status === 'failed' ? '✗ Failed' :
                           `${fileData.progress}%`}
                        </small>
                      </div>
                      <div className="progress" style={{ height: '6px' }}>
                        <div
                          className={`progress-bar ${
                            fileData.status === 'completed' ? 'bg-success' :
                            fileData.status === 'failed' ? 'bg-danger' :
                            'progress-bar-striped progress-bar-animated'
                          }`}
                          role="progressbar"
                          style={{ width: `${fileData.status === 'failed' ? 100 : fileData.progress}%` }}
                          aria-valuenow={fileData.progress}
                          aria-valuemin="0"
                          aria-valuemax="100"
                        ></div>
                      </div>
                    </div>
                  ))}
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
              <div className="card-header bg-white d-flex justify-content-between align-items-center">
                <h6 className="mb-0">
                  <i className="bi bi-list-check text-success me-2"></i>
                  Upload Results ({results.filter(r => r.success).length} / {results.length} succeeded)
                </h6>
              </div>
              <div className="card-body p-3" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {results.map((result, index) => (
                  <div
                    key={index}
                    className={`alert ${
                      result.success ? 'alert-success' : 'alert-danger'
                    } mb-2`}
                  >
                    <div className="d-flex align-items-start">
                      <i className={`bi ${
                        result.success ? 'bi-check-circle-fill' : 'bi-x-circle-fill'
                      } fs-5 me-3`}></i>
                      <div className="flex-grow-1">
                        <h6 className="alert-heading mb-2">{result.fileName}</h6>

                        {result.success ? (
                          <>
                            <p className="mb-2 small">{result.message}</p>

                            {result.stats && (
                              <div className="d-flex gap-2 mb-2 flex-wrap">
                                {result.stats.total_licenses > 0 && (
                                  <small className="badge bg-success">
                                    <i className="bi bi-card-list me-1"></i>
                                    {result.stats.total_licenses || 0} Licenses
                                  </small>
                                )}
                                {result.stats.files_processed > 0 && (
                                  <small className="badge bg-primary">
                                    <i className="bi bi-file-earmark-check me-1"></i>
                                    {result.stats.files_processed || 0} Files
                                  </small>
                                )}
                              </div>
                            )}

                            {result.licenses && result.licenses.length > 0 && (
                              <details className="mt-2">
                                <summary className="cursor-pointer small fw-bold">
                                  <i className="bi bi-card-checklist me-1"></i>
                                  View License Numbers ({result.licenses.length})
                                </summary>
                                <div className="d-flex flex-wrap gap-1 mt-2">
                                  {result.licenses.map((license, idx) => (
                                    <span key={idx} className="badge bg-success bg-opacity-75">
                                      {license}
                                    </span>
                                  ))}
                                </div>
                              </details>
                            )}
                          </>
                        ) : (
                          <p className="mb-0 small text-danger">
                            <i className="bi bi-exclamation-triangle me-1"></i>
                            {result.error}
                          </p>
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
