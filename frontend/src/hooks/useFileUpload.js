/**
 * useFileUpload Hook
 *
 * Comprehensive file upload hook that consolidates file upload logic
 * across the app (used by LedgerUpload.jsx and other upload pages).
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
import { toast } from "sonner";
import api from '../api/axios';

const DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024;
const ABSOLUTE_OR_PROTOCOL_RELATIVE_URL = /^(?:[a-z][a-z\d+.-]*:)?\/\//i;

function hasUnsafePathCharacters(path) {
  return [...path].some((char) => {
    const code = char.charCodeAt(0);
    return char === "\\" || code < 32 || code === 127;
  });
}

function normalizeUploadEndpoint(endpoint) {
  const value = String(endpoint ?? "").trim();

  if (!value) {
    throw new Error("Upload endpoint not configured");
  }
  if (ABSOLUTE_OR_PROTOCOL_RELATIVE_URL.test(value)) {
    throw new Error("Upload endpoint must be relative to the API origin");
  }
  if (hasUnsafePathCharacters(value)) {
    throw new Error("Upload endpoint contains unsafe characters");
  }

  return value;
}

function normalizeMaxFileSize(maxFileSize) {
  const size = Number(maxFileSize);
  return Number.isFinite(size) && size > 0 ? size : DEFAULT_MAX_FILE_SIZE;
}

function getFilesFromEvent(event) {
  return Array.from(event?.target?.files ?? event?.dataTransfer?.files ?? []);
}

function getUploadProgress(progressEvent) {
  const loaded = Number(progressEvent?.loaded);
  const total = Number(progressEvent?.total);

  if (!Number.isFinite(loaded) || !Number.isFinite(total) || total <= 0) {
    return 0;
  }

  return Math.min(100, Math.max(0, Math.round((loaded * 100) / total)));
}

function getResponseData(response) {
  return response?.data && typeof response.data === "object" ? response.data : {};
}

function getUploadErrorMessage(err, fallback) {
  const responseData = err?.response?.data;
  const responseError = typeof responseData?.error === "string" ? responseData.error.trim() : "";
  const responseDetail = typeof responseData?.detail === "string" ? responseData.detail.trim() : "";
  const errorMessage = typeof err?.message === "string" ? err.message.trim() : "";

  return responseError || responseDetail || errorMessage || fallback;
}

export const useFileUpload = (options = {}) => {
  const {
    endpoint,
    multiple = true,
    accept = '.csv',
    maxFileSize = DEFAULT_MAX_FILE_SIZE,
    fileFieldName = 'file', // Field name for FormData
    uploadMode = 'sequential', // 'sequential' or 'batch' (all files in one request)
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
  const effectiveMaxFileSize = normalizeMaxFileSize(maxFileSize);

  /**
   * Validate a single file
   */
  const validateFile = useCallback((file) => {
    if (!file || typeof file.name !== "string") {
      return {
        valid: false,
        error: "Invalid file selected"
      };
    }

    const fileSize = Number(file.size);
    if (!Number.isFinite(fileSize) || fileSize < 0) {
      return {
        valid: false,
        error: `File "${file.name}" has invalid size`
      };
    }

    // Check file size
    if (fileSize > effectiveMaxFileSize) {
      const sizeInMB = (effectiveMaxFileSize / (1024 * 1024)).toFixed(0);
      return {
        valid: false,
        error: `File "${file.name}" exceeds ${sizeInMB}MB size limit`
      };
    }

    // Check file type
    if (accept && accept !== '*') {
      const acceptedTypes = String(accept).split(',').map(t => t.trim().toLowerCase()).filter(Boolean);
      const fileName = file.name.toLowerCase();
      const fileType = String(file.type ?? '').toLowerCase();
      const isValid = acceptedTypes.some(type => {
        if (type.startsWith('.')) {
          return fileName.endsWith(type);
        }
        return fileType === type;
      });

      if (!isValid) {
        return {
          valid: false,
          error: `File "${file.name}" has invalid type. Expected: ${accept}`
        };
      }
    }

    return { valid: true };
  }, [effectiveMaxFileSize, accept]);

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

    const droppedFiles = getFilesFromEvent(e);
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
    const selectedFiles = getFilesFromEvent(e);
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
    if (e?.target) {
      e.target.value = '';
    }
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

    let uploadEndpoint;
    try {
      uploadEndpoint = normalizeUploadEndpoint(endpoint);
    } catch (err) {
      const errorMsg = err.message;
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

    if (uploadMode === 'batch') {
      // Upload all files in a single request
      const formData = new FormData();
      files.forEach(file => {
        formData.append(fileFieldName, file);
      });

      // Initialize progress for all files
      files.forEach((file, i) => {
        setFileProgress(prev => ({
          ...prev,
          [i]: { name: file.name, progress: 0, status: 'uploading' }
        }));
      });

      try {
        const response = await api.post(uploadEndpoint, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout,
          onUploadProgress: (progressEvent) => {
            const percentCompleted = getUploadProgress(progressEvent);
            // Update all files with same progress
            files.forEach((file, i) => {
              setFileProgress(prev => ({
                ...prev,
                [i]: { ...prev[i], progress: percentCompleted }
              }));
            });
          },
        });

        // Mark all as completed
        files.forEach((file, i) => {
          setFileProgress(prev => ({
            ...prev,
            [i]: { ...prev[i], progress: 100, status: 'completed' }
          }));
        });

        const responseData = getResponseData(response);
        uploadResults.push({
          fileName: files.length > 1 ? `${files.length} files` : files[0].name,
          success: true,
          message: typeof responseData.message === "string" && responseData.message.trim()
            ? responseData.message
            : 'Files processed successfully',
          licenses: Array.isArray(responseData.licenses) ? responseData.licenses : [],
          stats: responseData.stats && typeof responseData.stats === "object" ? responseData.stats : {},
          data: responseData,
        });

      } catch (err) {
        // Mark all as failed
        files.forEach((file, i) => {
          setFileProgress(prev => ({
            ...prev,
            [i]: { ...prev[i], progress: 0, status: 'failed' }
          }));
        });

        const errorMsg = getUploadErrorMessage(err, 'Failed to process files');

        uploadResults.push({
          fileName: files.length > 1 ? `${files.length} files` : files[0].name,
          success: false,
          error: errorMsg
        });
      }
    } else {
      // Upload files sequentially (original behavior)
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
          formData.append(fileFieldName, file);

          const response = await api.post(uploadEndpoint, formData, {
            headers: { 'Content-Type': 'multipart/form-data' },
            timeout,
            onUploadProgress: (progressEvent) => {
              const percentCompleted = getUploadProgress(progressEvent);
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

          const responseData = getResponseData(response);
          uploadResults.push({
            fileName: file.name,
            success: true,
            message: typeof responseData.message === "string" && responseData.message.trim()
              ? responseData.message
              : 'File processed successfully',
            licenses: Array.isArray(responseData.licenses) ? responseData.licenses : [],
            stats: responseData.stats && typeof responseData.stats === "object" ? responseData.stats : {},
            data: responseData,
          });

        } catch (err) {
          // Mark as failed
          setFileProgress(prev => ({
            ...prev,
            [i]: { ...prev[i], progress: 0, status: 'failed' }
          }));

          const errorMsg = getUploadErrorMessage(err, 'Failed to process file');

          uploadResults.push({
            fileName: file.name,
            success: false,
            error: errorMsg
          });
        }
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

    const failedCount = uploadResults.filter(r => !r.success).length;

    if (hasFailure) {
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
  }, [files, endpoint, timeout, onSuccess, onError, fileFieldName, uploadMode]);

  /**
   * Format file size for display
   */
  const formatFileSize = useCallback((bytes) => {
    const numericBytes = Number(bytes);
    if (!Number.isFinite(numericBytes) || numericBytes <= 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.min(sizes.length - 1, Math.floor(Math.log(numericBytes) / Math.log(k)));
    return Math.round((numericBytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
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
    setCurrentFileIndex(0);
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
