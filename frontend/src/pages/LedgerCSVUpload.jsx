import React, { useState } from 'react';
import api from '../api/axios';
import { useFileUpload } from '../hooks';

const LedgerCSVUpload = () => {
  const [showTemplate, setShowTemplate] = useState(false);
  const [templateInfo, setTemplateInfo] = useState(null);

  // Use the useFileUpload hook for single file upload
  const {
    files,
    uploading,
    results,
    error,
    handleFileChange,
    handleUpload,
    removeFile,
  } = useFileUpload({
    endpoint: '/api/licenses/ledger-csv-upload/',
    fileFieldName: 'file',
    multiple: false, // Single file mode
    accept: '.csv',
    onSuccess: (results) => {
      // Clear file input after successful upload
      const fileInput = document.getElementById('file-input');
      if (fileInput && results.some(r => r.success)) {
        fileInput.value = '';
      }
    },
  });

  // Single file reference (for UI display)
  const file = files && files.length > 0 ? files[0] : null;
  const result = results && results.length > 0 ? results[0] : null;

  const fetchTemplateInfo = async () => {
    try {
      const response = await api.get('/api/licenses/ledger-csv-upload/');
      setTemplateInfo(response.data);
      setShowTemplate(true);
    } catch (err) {
      // Error handled by hook
    }
  };

  const downloadTemplate = () => {
    const headers = ['DFIA', 'sr_no', 'BENO', 'BEDT', 'PORT', 'CIFINR', 'CIFD', 'QTY'];
    const exampleRow = ['0311031558', '1', '1234567', '01/01/2024', 'INMUN1', '10000.50', '1500.25', '1000'];

    const csvContent = [
      headers.join(','),
      exampleRow.join(',')
    ].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'ledger_template.csv';
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
              <i className="bi bi-file-earmark-text" style={{fontSize: '1.5rem'}}></i>
              Custom Ledger CSV Upload
            </h1>
            <p className="text-gray-600 mt-1">Import DFIA debit transactions from CSV file</p>
          </div>
          <button
            onClick={fetchTemplateInfo}
            className="flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition"
          >
            <i className="bi bi-info-circle"></i>
            View Instructions
          </button>
        </div>

        {/* Template Information Modal */}
        {showTemplate && templateInfo && (
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-semibold text-blue-900">CSV Format Instructions</h3>
              <button
                onClick={() => setShowTemplate(false)}
                className="text-blue-600 hover:text-blue-800"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <h4 className="font-semibold text-gray-700 mb-2">Required Headers:</h4>
                <div className="bg-white rounded p-3 font-mono text-sm">
                  {templateInfo.required_headers.join(', ')}
                </div>
              </div>

              <div>
                <h4 className="font-semibold text-gray-700 mb-2">Header Descriptions:</h4>
                <ul className="bg-white rounded p-3 space-y-1 text-sm">
                  {Object.entries(templateInfo.header_descriptions).map(([key, value]) => (
                    <li key={key}>
                      <span className="font-mono font-semibold">{key}:</span> {value}
                    </li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="font-semibold text-gray-700 mb-2">Notes:</h4>
                <ul className="bg-white rounded p-3 space-y-1 text-sm list-disc list-inside">
                  {templateInfo.notes.map((note, idx) => (
                    <li key={idx}>{note}</li>
                  ))}
                </ul>
              </div>

              <button
                onClick={downloadTemplate}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition w-full justify-center"
              >
                <i className="bi bi-download"></i>
                Download Template CSV
              </button>
            </div>
          </div>
        )}

        {/* File Upload Section */}
        <div className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition">
            <i className="bi bi-cloud-upload text-gray-400 mb-4" style={{fontSize: '3rem'}}></i>
            <label htmlFor="file-input" className="cursor-pointer">
              <span className="text-blue-600 hover:text-blue-700 font-semibold">
                Click to upload
              </span>
              <span className="text-gray-600"> or drag and drop</span>
              <p className="text-sm text-gray-500 mt-2">CSV files only</p>
            </label>
            <input
              id="file-input"
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
            />
          </div>

          {file && (
            <div className="flex items-center justify-between bg-gray-50 p-4 rounded-lg">
              <div className="flex items-center gap-3">
                <i className="bi bi-file-earmark-text text-blue-600" style={{fontSize: '1.25rem'}}></i>
                <div>
                  <p className="font-medium text-gray-800">{file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  removeFile(0);
                  document.getElementById('file-input').value = '';
                }}
                className="text-red-600 hover:text-red-800"
              >
                Remove
              </button>
            </div>
          )}

          <button
            onClick={handleUpload}
            disabled={!file || uploading}
            className={`w-full py-3 px-6 rounded-lg font-semibold transition flex items-center justify-center gap-2 ${
              !file || uploading
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-blue-600 text-white hover:bg-blue-700'
            }`}
          >
            {uploading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                Processing...
              </>
            ) : (
              <>
                <i className="bi bi-cloud-upload"></i>
                Upload and Process
              </>
            )}
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
            <i className="bi bi-exclamation-circle text-red-600" style={{fontSize: '1.25rem'}}></i>
            <div className="flex-1">
              <h3 className="font-semibold text-red-900">Error</h3>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Success Result */}
        {result && result.success && (
          <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <i className="bi bi-check-circle text-green-600" style={{fontSize: '1.25rem'}}></i>
              <div className="flex-1">
                <h3 className="font-semibold text-green-900">{result.message || result.data?.message}</h3>
                {result.data && (
                  <div className="mt-3 space-y-2 text-sm">
                    <p className="text-green-700">
                      ✓ Successfully processed: <span className="font-semibold">{result.data.success_count}</span> rows
                    </p>
                    {result.data.error_count > 0 && (
                      <p className="text-red-600">
                        ✗ Errors: <span className="font-semibold">{result.data.error_count}</span> rows
                      </p>
                    )}
                    {result.data.warning_count > 0 && (
                      <p className="text-yellow-600">
                        ⚠ Warnings: <span className="font-semibold">{result.data.warning_count}</span>
                      </p>
                    )}
                  </div>
                )}

                {result.data?.errors && result.data.errors.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-semibold text-red-900 mb-2">Errors:</h4>
                    <div className="bg-white rounded p-3 max-h-60 overflow-y-auto">
                      {result.data.errors.map((err, idx) => (
                        <div key={idx} className="text-sm text-red-700 py-2 border-b last:border-b-0">
                          <span className="font-semibold">Row {err.row}:</span> {err.error}
                        </div>
                      ))}
                    </div>
                    {result.data.note && (
                      <p className="text-sm text-gray-600 mt-2">{result.data.note}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Error Result */}
        {result && !result.success && (
          <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
            <i className="bi bi-exclamation-circle text-red-600" style={{fontSize: '1.25rem'}}></i>
            <div className="flex-1">
              <h3 className="font-semibold text-red-900">Upload Failed</h3>
              <p className="text-red-700 text-sm mt-1">{result.error}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LedgerCSVUpload;
