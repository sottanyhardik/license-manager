/**
 * Hook for managing MUI DataGrid inline editing
 * Handles cell edit state, save/cancel logic, and error recovery
 */

import { useState, useCallback } from 'react';
import { toast } from 'sonner';

interface EditingCell {
  rowId: any;
  columnName: string;
}

interface UseMuiDataGridEditingOptions {
  onInlineUpdate?: (id: any, columnName: string, value: any) => Promise<void>;
  inlineEditable?: string[];
}

export function useMuiDataGridEditing(options: UseMuiDataGridEditingOptions) {
  const { onInlineUpdate, inlineEditable = [] } = options;

  const [editingCell, setEditingCell] = useState<EditingCell | null>(null);
  const [editValue, setEditValue] = useState('');
  const [saving, setSaving] = useState(false);

  const handleCellClick = useCallback(
    (item: any, columnName: string) => {
      if (inlineEditable.includes(columnName)) {
        setEditingCell({ rowId: item.id, columnName });
        setEditValue(item[columnName] || '');
      }
    },
    [inlineEditable],
  );

  const handleSave = useCallback(
    async (item: any, columnName: string) => {
      if (!onInlineUpdate) return;
      setSaving(true);
      try {
        await onInlineUpdate(item.id, columnName, editValue);
        setEditingCell(null);
      } catch (error: any) {
        toast.error(error?.response?.data?.error || 'Failed to save. Please try again.');
      } finally {
        setSaving(false);
      }
    },
    [onInlineUpdate, editValue],
  );

  const handleCancel = useCallback(() => {
    setEditingCell(null);
    setEditValue('');
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent, item: any, columnName: string) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSave(item, columnName);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        handleCancel();
      }
    },
    [handleSave, handleCancel],
  );

  const isEditing = useCallback(
    (item: any, columnName: string) => editingCell?.rowId === item.id && editingCell?.columnName === columnName,
    [editingCell],
  );

  const handleBooleanToggle = useCallback(
    async (item: any, columnName: string, currentValue: boolean) => {
      setSaving(true);
      try {
        await onInlineUpdate?.(item.id, columnName, !currentValue);
      } catch (error: any) {
        toast.error(error?.response?.data?.error || 'Failed to update.');
      } finally {
        setSaving(false);
      }
    },
    [onInlineUpdate],
  );

  return {
    editingCell,
    editValue,
    saving,
    setEditValue,
    handleCellClick,
    handleSave,
    handleCancel,
    handleKeyDown,
    isEditing,
    handleBooleanToggle,
  };
}
