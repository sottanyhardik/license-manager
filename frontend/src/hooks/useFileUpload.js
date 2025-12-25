/**
 * useFileUpload Hook
 *
 * Comprehensive file upload hook that consolidates 780+ lines of duplicate
 * file upload logic from LedgerUpload.jsx and LedgerCSVUpload.jsx.
 *
 * Features:
 * - Drag and drop support
 * - File validation (size, type)
 * - Multiple file upload
 * - Upload progress tracking
 * - Success/error handling per file
 * - File size formatting
 *
 * @example
 * const {
 *   files,
 *   uploading,
 *   results,
 *   error,
 *   dragActive,
 *   fileProgress,
 *   handleDrag,
 *   handleDrop,
 *   handleFileChange,
 *   handleUpload,
 *   formatFileSize,
 * } = useFileUpload({
 *   endpoint: '/api/upload-ledger/',
 *   multiple: true,
 *   accept: '.csv',
 *   onSuccess: () => toast.success('Files uploaded'),
 * });
 */

import { useState, useCallback } from 'react';
import { toast } from 'react-toastify';
import api from '../api/axios';

export const useFileUpload = (options = {}) => {
  const {
    endpoint,
    multiple = true,
    accept = '.csv',
    maxFileSize = 50 * 1024 * 1024, // 50MB default
    onSuccess,
    onError,
    onFileAdded,
    timeout = 300000, // 5 minutes default
  } = options;

  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [results, setResults] = useState([]);
  const [error, setError] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [fileProgress, setFileProgress] = useState({});
  const [currentFileIndex, setCurrentFileIndex] = useState(0);

  /**
   * Validate a single file
   */
  const validateFile = useCallback((file) => {
    // Check file size
    if (file.size > maxFileSize) {
      const sizeInMB = (maxFileSize / (1024 * 1024)).toFixed(0);
      return {
        valid: false,
        error: `File "${file.name}" exceeds ${sizeInMB}MB size limit`
      };
    }

    // Check file type
    if (accept && accept !== '*') {
      const acceptedTypes = accept.split(',').map(t => t.trim().toLowerCase());
      const fileName = file.name.toLowerCase();
      const isValid = acceptedTypes.some(type => {
        if (type.startsWith('.')) {
          return fileName.endsWith(type);
        }
        return file.type === type;
      });

      if (!isValid) {
        return {
          valid: false,
          error: `File "${file.name}" has invalid type. Expected: ${accept}`
        };
      }
    }

    return { valid: true };
  }, [maxFileSize, accept]);

  /**
   * Handle drag events
   */
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();

    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  /**
   * Handle file drop
   */
  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles = [];
    const errors = [];

    droppedFiles.forEach(file => {
      const validation = validateFile(file);
      if (validation.valid) {
        validFiles.push(file);
      } else {
        errors.push(validation.error);
      }
    });

    if (validFiles.length > 0) {
      const filesToAdd = multiple ? validFiles : [validFiles[0]];
      setFiles(filesToAdd);
      setError(null);
      setResults([]);

      if (onFileAdded) {
        onFileAdded(filesToAdd);
      }
    }

    if (errors.length > 0) {
      const errorMsg = errors.join(', ');
      setError(errorMsg);
      toast.error(errorMsg);
    }
  }, [multiple, validateFile, onFileAdded]);

  /**
   * Handle file input change
   */
  const handleFileChange = useCallback((e) => {
    const selectedFiles = Array.from(e.target.files);
    const validFiles = [];
    const errors = [];

    selectedFiles.forEach(file => {
      const validation = validateFile(file);
      if (validation.valid) {
        validFiles.push(file);
      } else {
        errors.push(validation.error);
      }
    });

    if (validFiles.length > 0) {
      const filesToAdd = multiple ? validFiles : [validFiles[0]];
      setFiles(filesToAdd);
      setError(null);
      setResults([]);

      if (onFileAdded) {
        onFileAdded(filesToAdd);
      }
    }

    if (errors.length > 0) {
      const errorMsg = errors.join(', ');
      setError(errorMsg);
      toast.error(errorMsg);
    }

    // Reset input value to allow selecting the same file again
    e.target.value = '';
  }, [multiple, validateFile, onFileAdded]);

  /**
   * Upload files to server
   */
  const handleUpload = useCallback(async () => {
    if (files.length === 0) {
      const errorMsg = 'Please select at least one file';
      setError(errorMsg);
      toast.error(errorMsg);
      return { success: false, error: errorMsg };
    }

    if (!endpoint) {
      const errorMsg = 'Upload endpoint not configured';
      setError(errorMsg);
      toast.error(errorMsg);
      return { success: false, error: errorMsg };
    }

    setUploading(true);
    setError(null);
    setResults([]);
    setFileProgress({});
    setCurrentFileIndex(0);

    const uploadResults = [];

    // Upload files sequentially
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setCurrentFileIndex(i + 1);

      // Initialize progress for this file
      setFileProgress(prev => ({
        ...prev,
        [i]: { name: file.name, progress: 0, status: 'uploading' }
      }));

      try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await api.post(endpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout,
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            setFileProgress(prev => ({
              ...prev,
              [i]: { ...prev[i], progress: percentCompleted }
            }));
          },
        });

        // Mark as completed
        setFileProgress(prev => ({
          ...prev,
          [i]: { ...prev[i], progress: 100, status: 'completed' }
        }));

        uploadResults.push({
          fileName: file.name,
          success: true,
          message: response.data.message || 'File processed successfully',
          data: response.data,
        });

      } catch (err) {
        // Mark as failed
        setFileProgress(prev => ({
          ...prev,
          [i]: { ...prev[i], progress: 0, status: 'failed' }
        }));

        const errorMsg = err.response?.data?.error
          || err.response?.data?.detail
          || err.message
          || 'Failed to process file';

        uploadResults.push({
          fileName: file.name,
          success: false,
          error: errorMsg
        });
      }
    }

    setResults(uploadResults);

    // Check if any uploads succeeded
    const hasSuccess = uploadResults.some(r => r.success);
    const hasFailure = uploadResults.some(r => !r.success);

    if (hasSuccess) {
      setFiles([]); // Clear successful files
      toast.success(
        `${uploadResults.filter(r => r.success).length} file(s) uploaded successfully`
      );

      if (onSuccess) {
        onSuccess(uploadResults);
      }
    }

    if (hasFailure) {
      const failedCount = uploadResults.filter(r => !r.success).length;
      toast.error(`${failedCount} file(s) failed to upload`);

      if (onError) {
        onError(uploadResults.filter(r => !r.success));
      }
    }

    setUploading(false);
    setCurrentFileIndex(0);

    return {
      success: hasSuccess,
      results: uploadResults,
      successCount: uploadResults.filter(r => r.success).length,
      failureCount: failedCount,
    };
  }, [files, endpoint, timeout, onSuccess, onError]);

  /**
   * Format file size for display
   */
  const formatFileSize = useCallback((bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
  }, []);

  /**
   * Remove a file from the list
   */
  const removeFile = useCallback((index) => {
    setFiles(prev => prev.filter((_, i) => i !== index));
  }, []);

  /**
   * Clear all files and reset state
   */
  const clearFiles = useCallback(() => {
    setFiles([]);
    setResults([]);
    setError(null);
    setFileProgress({});
  }, []);

  return {
    files,
    uploading,
    results,
    error,
    dragActive,
    fileProgress,
    currentFileIndex,
    handleDrag,
    handleDrop,
    handleFileChange,
    handleUpload,
    formatFileSize,
    removeFile,
    clearFiles,
    setFiles,
    setError,
  };
};

export default useFileUpload;
