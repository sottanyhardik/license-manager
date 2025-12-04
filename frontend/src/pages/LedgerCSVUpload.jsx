import React, { useState } from 'react';
import { Upload, FileText, AlertCircle, CheckCircle, Download, Info } from 'lucide-react';
import api from '../services/api';

const LedgerCSVUpload = () => {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [showTemplate, setShowTemplate] = useState(false);
  const [templateInfo, setTemplateInfo] = useState(null);

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      if (!selectedFile.name.endsWith('.csv')) {
        setError('Please select a CSV file');
        setFile(null);
        return;
      }
      setFile(selectedFile);
      setError(null);
      setResult(null);
    }
  };

  const fetchTemplateInfo = async () => {
    try {
      const response = await api.get('/api/licenses/ledger-csv-upload/');
      setTemplateInfo(response.data);
      setShowTemplate(true);
    } catch (err) {
      setError('Failed to fetch template information');
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

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setUploading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await api.post('/api/licenses/ledger-csv-upload/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setResult(response.data);
      setFile(null);
      // Reset file input
      document.getElementById('file-input').value = '';
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to upload file');
      setResult(err.response?.data);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="bg-white rounded-lg shadow-lg p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-800 flex items-center gap-2">
              <FileText className="w-6 h-6" />
              Custom Ledger CSV Upload
            </h1>
            <p className="text-gray-600 mt-1">Import DFIA debit transactions from CSV file</p>
          </div>
          <button
            onClick={fetchTemplateInfo}
            className="flex items-center gap-2 px-4 py-2 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 transition"
          >
            <Info className="w-4 h-4" />
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
                <Download className="w-4 h-4" />
                Download Template CSV
              </button>
            </div>
          </div>
        )}

        {/* File Upload Section */}
        <div className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-400 transition">
            <Upload className="w-12 h-12 mx-auto text-gray-400 mb-4" />
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
                <FileText className="w-5 h-5 text-blue-600" />
                <div>
                  <p className="font-medium text-gray-800">{file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.size / 1024).toFixed(2)} KB
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setFile(null);
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
                <Upload className="w-5 h-5" />
                Upload and Process
              </>
            )}
          </button>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mt-6 bg-red-50 border border-red-200 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-red-600 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-red-900">Error</h3>
              <p className="text-red-700 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* Success Result */}
        {result && !error && (
          <div className="mt-6 bg-green-50 border border-green-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-green-600 mt-0.5" />
              <div className="flex-1">
                <h3 className="font-semibold text-green-900">{result.message}</h3>
                <div className="mt-3 space-y-2 text-sm">
                  <p className="text-green-700">
                    ✓ Successfully processed: <span className="font-semibold">{result.success_count}</span> rows
                  </p>
                  {result.error_count > 0 && (
                    <p className="text-red-600">
                      ✗ Errors: <span className="font-semibold">{result.error_count}</span> rows
                    </p>
                  )}
                  {result.warning_count > 0 && (
                    <p className="text-yellow-600">
                      ⚠ Warnings: <span className="font-semibold">{result.warning_count}</span>
                    </p>
                  )}
                </div>

                {result.errors && result.errors.length > 0 && (
                  <div className="mt-4">
                    <h4 className="font-semibold text-red-900 mb-2">Errors:</h4>
                    <div className="bg-white rounded p-3 max-h-60 overflow-y-auto">
                      {result.errors.map((err, idx) => (
                        <div key={idx} className="text-sm text-red-700 py-2 border-b last:border-b-0">
                          <span className="font-semibold">Row {err.row}:</span> {err.error}
                        </div>
                      ))}
                    </div>
                    {result.note && (
                      <p className="text-sm text-gray-600 mt-2">{result.note}</p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LedgerCSVUpload;
