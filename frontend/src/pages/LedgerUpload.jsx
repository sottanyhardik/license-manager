import React, { useState, useEffect } from 'react';
import { useFileUpload } from '../hooks';
import axios from 'axios';
import api from '../api/axios';

// Defined outside LedgerUpload so React doesn't remount it on every parent render,
// which would destroy polling intervals.
const TaskStatusModal = ({ fileTasks, show, onHide }) => {
  const [taskStatuses, setTaskStatuses] = useState({});

  useEffect(() => {
    if (!show || fileTasks.length === 0) return;

    const allTasks = fileTasks.flatMap(f => f.tasks);
    const intervals = [];

    allTasks.forEach((task) => {
      const interval = setInterval(async () => {
        try {
          const response = await api.get(`ledger-task-status/${task.task_id}/`);
          setTaskStatuses((prev) => ({ ...prev, [task.task_id]: response.data }));
          if (response.data.state === 'SUCCESS' || response.data.state === 'FAILURE') {
            clearInterval(interval);
          }
        } catch (err) {
          console.error('Error fetching task status:', err);
        }
      }, 2000);
      intervals.push(interval);
    });

    return () => intervals.forEach(clearInterval);
  }, [fileTasks, show]);

  // Reset statuses when a new batch of tasks comes in
  useEffect(() => {
    setTaskStatuses({});
  }, [fileTasks]);

  if (!show) return null;

  return (
    <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.6)' }}>
      <div className="modal-dialog modal-lg modal-dialog-scrollable">
        <div className="modal-content" style={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 40px rgba(0,0,0,0.2)' }}>
          <div className="modal-header" style={{ background: 'linear-gradient(135deg,#4F46E5,#4338CA)', color: 'white', borderRadius: '12px 12px 0 0', borderBottom: 'none', padding: '1.25rem 1.5rem' }}>
            <h5 className="modal-title fw-semibold">
              <i className="bi bi-gear-fill me-2"></i>
              Processing Ledger Files
            </h5>
            <button type="button" className="btn-close btn-close-white" onClick={onHide}></button>
          </div>
          <div className="modal-body">
            {fileTasks.map((fileEntry, fi) => {
              const total = fileEntry.total;
              const done = fileEntry.tasks.filter(t => taskStatuses[t.task_id]?.state === 'SUCCESS').length;
              const failed = fileEntry.tasks.filter(t => taskStatuses[t.task_id]?.state === 'FAILURE').length;
              const pending = total - done - failed;
              const pct = total > 0 ? Math.round(((done + failed) / total) * 100) : 0;
              const allDone = pending === 0;

              return (
                <div key={fi} className="card mb-3">
                  <div className="card-body">
                    <div className="d-flex justify-content-between align-items-center mb-2">
                      <h6 className="mb-0">
                        <i className="bi bi-file-earmark-text me-2"></i>
                        {fileEntry.file}
                      </h6>
                      <span className={`badge ${allDone ? (failed > 0 ? 'bg-warning' : 'bg-success') : 'bg-primary'}`}>
                        {allDone ? 'Done' : `Processing ${done + failed}/${total}`}
                      </span>
                    </div>

                    <div className="progress mb-2" style={{ height: '8px' }}>
                      <div
                        className={`progress-bar ${!allDone ? 'progress-bar-striped progress-bar-animated' : failed === 0 ? 'bg-success' : 'bg-warning'}`}
                        style={{ width: `${pct}%` }}
                      />
                    </div>

                    <div className="d-flex gap-3 small mb-2">
                      <span className="text-success">
                        <i className="bi bi-check-circle me-1"></i>{done} done
                      </span>
                      {failed > 0 && (
                        <span className="text-danger">
                          <i className="bi bi-x-circle me-1"></i>{failed} failed
                        </span>
                      )}
                      {pending > 0 && (
                        <span className="text-muted">
                          <i className="bi bi-hourglass-split me-1"></i>{pending} pending
                        </span>
                      )}
                      <span className="ms-auto text-muted">{pct}%</span>
                    </div>

                    <details>
                      <summary className="small fw-bold" style={{ cursor: 'pointer' }}>
                        Licenses ({total})
                      </summary>
                      <div className="d-flex flex-wrap gap-1 mt-2">
                        {fileEntry.tasks.map((task) => {
                          const s = taskStatuses[task.task_id];
                          const isOk = s?.state === 'SUCCESS';
                          const isFail = s?.state === 'FAILURE';
                          return (
                            <span
                              key={task.task_id}
                              className={`badge ${isOk ? 'bg-success' : isFail ? 'bg-danger' : 'bg-secondary'}`}
                              title={isFail ? s?.error : isOk ? 'Processed' : 'Pending'}
                            >
                              {task.license}
                            </span>
                          );
                        })}
                      </div>
                    </details>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="modal-footer">
            <button type="button" className="btn btn-secondary" onClick={onHide}>Close</button>
          </div>
        </div>
      </div>
    </div>
  );
};

const LedgerUpload = () => {
  const [asyncFileTasks, setAsyncFileTasks] = useState([]);
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
    endpoint: 'upload-ledger/',
    fileFieldName: 'ledger',
    uploadMode: 'sequential',
    multiple: true,
    accept: '.csv',
    maxFileSize: 50 * 1024 * 1024,
    timeout: 300000,
    onSuccess: (results) => {
      const fileInput = document.getElementById('file-input');
      if (fileInput && results.some(r => r.success)) {
        fileInput.value = '';
      }
    },
  });

  const handleAsyncUpload = async () => {
    if (files.length === 0) return;

    const formData = new FormData();
    files.forEach((file) => {
      formData.append('ledger', file);
    });
    formData.append('async', 'true');

    try {
      const response = await api.post('upload-ledger/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      if (response.data.file_tasks) {
        setAsyncFileTasks(response.data.file_tasks);
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

  return (
    <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
      {/* Compact Header */}
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
            <i className="bi bi-file-earmark-spreadsheet me-2" style={{ color: '#4F46E5' }}></i>
            Ledger Upload
          </h4>
          <small className="text-muted">Upload DFIA license ledger files in CSV format</small>
        </div>
        <div className="form-check form-switch mb-0">
          <input
            className="form-check-input"
            type="checkbox"
            role="switch"
            id="asyncModeSwitch"
            checked={useAsyncMode}
            onChange={(e) => setUseAsyncMode(e.target.checked)}
            style={{ width: '2.5rem', height: '1.25rem', cursor: 'pointer' }}
          />
          <label className="form-check-label small fw-medium" htmlFor="asyncModeSwitch" style={{ cursor: 'pointer' }}>
            <i className="bi bi-lightning-charge-fill me-1 text-warning"></i>
            Async {useAsyncMode ? '(Parallel)' : '(Sync)'}
          </label>
        </div>
      </div>

      <TaskStatusModal
        fileTasks={asyncFileTasks}
        show={showTaskModal}
        onHide={() => setShowTaskModal(false)}
      />

      <div className="row g-3">
        {/* Main Upload Card */}
        <div className="col-lg-8">
          <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
            <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
              <h6 className="mb-0 fw-semibold">
                <i className="bi bi-cloud-upload me-2" style={{ color: '#4F46E5' }}></i>
                Upload Files
              </h6>
            </div>
            <div className="card-body" style={{ padding: '24px' }}>
              {/* Drop Zone */}
              <div
                className={`border-2 border-dashed rounded p-5 text-center mb-4 ${
                  dragActive ? 'border-primary bg-primary bg-opacity-10' : 'border-secondary bg-light'
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
                  <i className={`bi bi-cloud-arrow-up display-1 ${dragActive ? 'text-primary' : 'text-muted'}`}></i>
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
                      <div key={index} className="list-group-item d-flex justify-content-between align-items-center">
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

              {/* Upload Progress (sync mode) */}
              {uploading && Object.keys(fileProgress).length > 0 && (
                <div className="mb-4">
                  <h6 className="mb-2">
                    <i className="bi bi-cloud-upload me-2"></i>
                    Uploading Files
                  </h6>
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

          {/* Results Section (sync mode) */}
          {results.length > 0 && (
            <div className="card border-0 shadow-sm mt-3" style={{ borderRadius: '12px' }}>
              <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                <h6 className="mb-0 fw-semibold">
                  <i className="bi bi-list-check me-2" style={{ color: '#10b981' }}></i>
                  Upload Results
                  <span className="badge ms-2" style={{ backgroundColor: '#d1fae5', color: '#065f46', fontSize: '0.7rem' }}>
                    {results.filter(r => r.success).length}/{results.length} succeeded
                  </span>
                </h6>
              </div>
              <div className="card-body p-3" style={{ maxHeight: '500px', overflowY: 'auto' }}>
                {results.map((result, index) => (
                  <div key={index} className={`alert ${result.success ? 'alert-success' : 'alert-danger'} mb-2`}>
                    <div className="d-flex align-items-start">
                      <i className={`bi ${result.success ? 'bi-check-circle-fill' : 'bi-x-circle-fill'} fs-5 me-3`}></i>
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
                                    {result.stats.total_licenses} Licenses
                                  </small>
                                )}
                              </div>
                            )}
                            {result.licenses && result.licenses.length > 0 && (
                              <details className="mt-2">
                                <summary className="cursor-pointer small fw-bold">
                                  View License Numbers ({result.licenses.length})
                                </summary>
                                <div className="d-flex flex-wrap gap-1 mt-2">
                                  {result.licenses.map((license, idx) => (
                                    <span key={idx} className="badge bg-success bg-opacity-75">{license}</span>
                                  ))}
                                </div>
                              </details>
                            )}
                            {result.data?.results?.[0]?.failed?.length > 0 && (
                              <details className="mt-2">
                                <summary className="cursor-pointer small fw-bold text-danger">
                                  Failed Licenses ({result.data.results[0].failed.length})
                                </summary>
                                <div className="mt-2">
                                  {result.data.results[0].failed.map((f, idx) => (
                                    <div key={idx} className="small text-danger mb-1">
                                      <strong>{f.license}:</strong> {f.error}
                                    </div>
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
          <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
            <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
              <h6 className="mb-0 fw-semibold">
                <i className="bi bi-info-circle me-2" style={{ color: '#4F46E5' }}></i>
                File Format Guide
              </h6>
            </div>
            <div className="card-body">
              <h6 className="mb-3">Required CSV Columns:</h6>
              <div className="mb-3">
                {['Regn.No.', 'Regn.Date', 'Lic.No.', 'Lic.Date', 'IEC', 'Scheme.Cd.', 'Port', 'Notification'].map(col => (
                  <div key={col} className="d-flex align-items-center mb-2">
                    <i className="bi bi-check-circle-fill text-success me-2"></i>
                    <code>{col}</code>
                  </div>
                ))}
              </div>
              <div className="alert alert-info mb-0">
                <h6 className="alert-heading">
                  <i className="bi bi-lightbulb me-2"></i>
                  Important Notes
                </h6>
                <ul className="mb-0 small ps-3">
                  <li className="mb-1">Date format: DD/MM/YYYY</li>
                  <li className="mb-1">License numbers zero-padded to 10 digits</li>
                  <li className="mb-1">Credit and Debit transactions auto-processed</li>
                  <li className="mb-1">Multiple files supported</li>
                  <li className="mb-1"><strong>Max file size: 50MB</strong></li>
                  <li className="mb-1"><strong>Async mode: each license runs in parallel</strong></li>
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
