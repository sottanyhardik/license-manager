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
  const [asyncError, setAsyncError] = useState(null);
  const [asyncUploading, setAsyncUploading] = useState(false);

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

    setAsyncError(null);
    setAsyncUploading(true);

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
      const msg = err.response?.data?.error || err.message || 'Upload failed. Please try again.';
      setAsyncError(msg);
    } finally {
      setAsyncUploading(false);
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
            <div className="card-header bg-white border-bottom py-2 px-3" style={{ borderRadius: '12px 12px 0 0' }}>
              <h6 className="mb-0 fw-semibold">
                <i className="bi bi-cloud-upload me-2" style={{ color: '#4F46E5' }}></i>
                Upload Files
              </h6>
            </div>
            <div className="card-body" style={{ padding: '24px' }}>
              {/* Drop Zone */}
              <label
                htmlFor="file-input"
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  border: `2px dashed ${dragActive ? '#4F46E5' : '#d1d5db'}`,
                  borderRadius: '12px',
                  padding: '36px 24px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  minHeight: '170px',
                  background: dragActive ? 'rgba(79,70,229,0.04)' : 'white',
                  transition: 'border-color 0.15s, background 0.15s',
                  marginBottom: '16px',
                }}
                onMouseEnter={e => { if (!dragActive) e.currentTarget.style.borderColor = '#4F46E5'; }}
                onMouseLeave={e => { if (!dragActive) e.currentTarget.style.borderColor = '#d1d5db'; }}
              >
                <i className="bi bi-cloud-arrow-up d-block mb-2" style={{ fontSize: '2.5rem', color: dragActive ? '#4F46E5' : '#9ca3af' }}></i>
                <p className="fw-semibold mb-1">{dragActive ? 'Drop files here' : 'Drag & drop your CSV files'}</p>
                <small className="text-muted mb-3">or click to browse</small>
                <span className="btn btn-sm" style={{ background: 'linear-gradient(135deg,#4F46E5,#4338CA)', color: 'white', border: 'none', pointerEvents: 'none', fontWeight: '600' }}>
                  <i className="bi bi-folder2-open me-1"></i>Browse Files
                </span>
                <small className="text-muted mt-3 d-block">CSV files only · Max 50MB per file</small>
                <input id="file-input" type="file" accept=".csv" multiple onChange={handleFileChange} className="d-none" />
              </label>

              {/* Selected Files List */}
              {files.length > 0 && (
                <div className="mb-4">
                  <div className="d-flex justify-content-between align-items-center mb-2">
                    <span className="fw-semibold small" style={{ color: 'var(--text-secondary)' }}>
                      <i className="bi bi-paperclip me-1"></i>
                      {files.length} file{files.length > 1 ? 's' : ''} selected
                    </span>
                    <button
                      className="btn btn-sm btn-outline-danger"
                      onClick={() => {
                        clearFiles();
                        document.getElementById('file-input').value = '';
                      }}
                      disabled={uploading}
                      style={{ fontSize: '0.75rem', padding: '2px 8px' }}
                    >
                      <i className="bi bi-trash me-1"></i>Clear All
                    </button>
                  </div>
                  <div className="d-flex flex-column gap-2">
                    {files.map((file, index) => (
                      <div key={index} className="d-flex align-items-center gap-2 px-2 py-2" style={{ background: 'var(--bs-gray-50)', borderRadius: '8px', border: '1px solid #e5e7eb' }}>
                        <i className="bi bi-file-earmark-text text-success" style={{ fontSize: '1.1rem', flexShrink: 0 }}></i>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div className="fw-medium small text-truncate">{file.name}</div>
                          <small className="text-muted">{formatFileSize(file.size)}</small>
                        </div>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-danger"
                          onClick={() => removeFile(index)}
                          disabled={uploading}
                          style={{ padding: '2px 8px', flexShrink: 0 }}
                        >
                          <i className="bi bi-x-lg"></i>
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Error Alert */}
              {(error || asyncError) && (
                <div className="alert alert-danger d-flex align-items-center mb-4" role="alert">
                  <i className="bi bi-exclamation-triangle-fill me-2"></i>
                  <div>{error || asyncError}</div>
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
                  disabled={files.length === 0 || uploading || asyncUploading}
                  style={{
                    background: files.length === 0 || uploading || asyncUploading ? undefined : 'linear-gradient(135deg,#4F46E5,#4338CA)',
                    border: 'none', fontWeight: '600', borderRadius: '10px', padding: '12px'
                  }}
                >
                  {(uploading || asyncUploading) ? (
                    <>
                      <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                      Uploading {files.length} file{files.length > 1 ? 's' : ''}...
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
              <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-2 px-3" style={{ borderRadius: '12px 12px 0 0' }}>
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
            <div className="card-header bg-white border-bottom py-2 px-3" style={{ borderRadius: '12px 12px 0 0' }}>
              <h6 className="mb-0 fw-semibold">
                <i className="bi bi-info-circle me-2" style={{ color: '#4F46E5' }}></i>
                File Format Guide
              </h6>
            </div>
            <div className="card-body">
              <div className="fw-semibold small mb-2" style={{ color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.3px', fontSize: '0.72rem' }}>Required CSV Columns</div>
              <div className="d-flex flex-wrap gap-1 mb-3">
                {['Regn.No.', 'Regn.Date', 'Lic.No.', 'Lic.Date', 'IEC', 'Scheme.Cd.', 'Port', 'Notification'].map(col => (
                  <code key={col} style={{ fontSize: '0.75rem', background: '#e0e7ff', color: '#4F46E5', padding: '2px 8px', borderRadius: '4px', border: '1px solid #c7d2fe' }}>{col}</code>
                ))}
              </div>
              <div style={{ background: '#fef3c7', borderRadius: '8px', padding: '12px 14px', border: '1px solid #fde68a' }}>
                <div className="fw-semibold small mb-2" style={{ color: '#92400e' }}>
                  <i className="bi bi-lightbulb me-1"></i>Important Notes
                </div>
                <ul className="mb-0 ps-3">
                  <li className="small text-muted mb-1">Date format: DD/MM/YYYY</li>
                  <li className="small text-muted mb-1">License numbers zero-padded to 10 digits</li>
                  <li className="small text-muted mb-1">Credit and Debit transactions auto-processed</li>
                  <li className="small text-muted mb-1">Multiple files supported · Max 50MB</li>
                  <li className="small text-muted mb-0"><strong>Async mode:</strong> each license runs in parallel</li>
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
