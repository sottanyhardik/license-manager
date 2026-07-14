/**
 * useConfirmDialog Hook
 *
 * Custom hook to manage confirmation dialogs
 * Makes it easy to replace window.confirm() with accessible ConfirmDialog
 *
 * @example
 * const { showConfirm, confirmDialog } = useConfirmDialog();
 *
 * const handleDelete = async () => {
 *   const confirmed = await showConfirm({
 *     title: 'Delete Record',
 *     message: 'Are you sure you want to delete this record?',
 *     severity: 'danger',
 *     confirmText: 'Delete'
 *   });
 *
 *   if (confirmed) {
 *     // Proceed with deletion
 *   }
 * };
 *
 * return (
 *   <>
 *     <button onClick={handleDelete}>Delete</button>
 *     {confirmDialog}
 *   </>
 * );
 */

import React, { useState, useCallback } from 'react';
import ConfirmDialog from '../components/ConfirmDialog';

export const useConfirmDialog = () => {
  const [dialogConfig, setDialogConfig] = useState<{
    show: boolean;
    title: string;
    message: string;
    severity: string;
    confirmText: string;
    cancelText: string;
    showCancelButton?: boolean;
    onConfirm: (() => void) | null;
    onCancel: (() => void) | null;
  }>({
    show: false,
    title: '',
    message: '',
    severity: 'warning',
    confirmText: 'Confirm',
    cancelText: 'Cancel',
    onConfirm: null,
    onCancel: null,
  });

  /**
   * Show a confirmation dialog and return a promise that resolves to true/false
   * @param {Object} config - Dialog configuration
   * @returns {Promise<boolean>} - Resolves to true if confirmed, false if cancelled
   */
  const showConfirm = useCallback((config) => {
    return new Promise((resolve) => {
      setDialogConfig({
        show: true,
        title: config.title || 'Confirm Action',
        message: config.message || 'Are you sure you want to proceed?',
        severity: config.severity || 'warning',
        confirmText: config.confirmText || 'Confirm',
        cancelText: config.cancelText || 'Cancel',
        showCancelButton: config.showCancelButton !== false,
        onConfirm: () => {
          setDialogConfig((prev) => ({ ...prev, show: false }));
          resolve(true);
        },
        onCancel: () => {
          setDialogConfig((prev) => ({ ...prev, show: false }));
          resolve(false);
        },
      });
    });
  }, []);

  /**
   * Shorthand for common dialog types
   */
  const confirmDelete = useCallback(
    (itemName = 'this record') => {
      return showConfirm({
        title: 'Delete Confirmation',
        message: `Are you sure you want to delete ${itemName}? This action cannot be undone.`,
        severity: 'danger',
        confirmText: 'Delete',
        cancelText: 'Cancel',
      });
    },
    [showConfirm]
  );

  const confirmAction = useCallback(
    (actionName, itemName = '') => {
      return showConfirm({
        title: `Confirm ${actionName}`,
        message: `Are you sure you want to ${actionName.toLowerCase()} ${itemName}?`,
        severity: 'warning',
        confirmText: actionName,
        cancelText: 'Cancel',
      });
    },
    [showConfirm]
  );

  const confirmDangerousAction = useCallback(
    (title, message) => {
      return showConfirm({
        title: title || 'Dangerous Action',
        message: message || 'This action is potentially dangerous and cannot be undone. Are you sure you want to proceed?',
        severity: 'danger',
        confirmText: 'Proceed',
        cancelText: 'Cancel',
      });
    },
    [showConfirm]
  );

  const confirmDialog = (
    <ConfirmDialog
      show={dialogConfig.show}
      title={dialogConfig.title}
      message={dialogConfig.message}
      severity={dialogConfig.severity}
      confirmText={dialogConfig.confirmText}
      cancelText={dialogConfig.cancelText}
      showCancelButton={dialogConfig.showCancelButton}
      onConfirm={dialogConfig.onConfirm}
      onCancel={dialogConfig.onCancel}
    />
  );

  return {
    showConfirm,
    confirmDelete,
    confirmAction,
    confirmDangerousAction,
    confirmDialog,
  };
};

export default useConfirmDialog;
