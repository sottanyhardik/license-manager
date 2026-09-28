import React from 'react';
import { TextField, Select, MenuItem, Stack, Button, Box } from '@mui/material';
import { X as XIcon } from 'lucide-react';

/**
 * Reusable MUI TextField for report filters
 */
export function ReportTextFilter({
  label,
  value,
  onChange,
  placeholder,
  type = 'text',
  fullWidth = true,
  required = false,
  error = false,
  helperText = '',
  disabled = false,
}: {
  label?: string;
  value: string | number;
  onChange: (value: string | number) => void;
  placeholder?: string;
  type?: string;
  fullWidth?: boolean;
  required?: boolean;
  error?: boolean;
  helperText?: string;
  disabled?: boolean;
}) {
  return (
    <TextField
      label={label}
      type={type}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      variant="outlined"
      size="small"
      fullWidth={fullWidth}
      required={required}
      error={error}
      helperText={helperText}
      disabled={disabled}
      slotProps={{
        input: {
          style: { fontSize: '0.875rem' },
        },
      }}
    />
  );
}

/**
 * Reusable MUI Select for report filters with multi-select support
 */
export function ReportSelectFilter({
  label,
  value,
  onChange,
  options,
  multiple = false,
  fullWidth = true,
  required = false,
  error = false,
  helperText = '',
  disabled = false,
}: {
  label?: string;
  value: string | string[] | number | number[];
  onChange: (value: string | string[] | number | number[]) => void;
  options: Array<{ label: string; value: string | number }>;
  multiple?: boolean;
  fullWidth?: boolean;
  required?: boolean;
  error?: boolean;
  helperText?: string;
  disabled?: boolean;
}) {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return (
    <TextField
      label={label}
      select
      value={value}
      onChange={(e: any) => onChange(e.target.value as any)}
      variant="outlined"
      size="small"
      fullWidth={fullWidth}
      required={required}
      error={error}
      helperText={helperText}
      disabled={disabled}
      SelectProps={{
        multiple,
      } as any}
      slotProps={{
        input: {
          style: { fontSize: '0.875rem' },
        } as any,
      } as any}
    >
      {options.map((option) => (
        <MenuItem key={option.value} value={option.value}>
          {option.label}
        </MenuItem>
      ))}
    </TextField>
  );
}

/**
 * Filter group with clear button
 */
export function ReportFilterBar({
  children,
  onClear,
  spacing = 2,
}: {
  children: React.ReactNode;
  onClear?: () => void;
  spacing?: number;
}) {
  return (
    <Box sx={{ display: 'flex', gap: spacing, alignItems: 'flex-end', flexWrap: 'wrap' }}>
      {children}
      {onClear && (
        <Button
          variant="outlined"
          size="small"
          onClick={onClear}
          startIcon={<XIcon className="size-4" />}
        >
          Clear Filters
        </Button>
      )}
    </Box>
  );
}

/**
 * Display active filters with clear buttons
 */
export function ActiveReportFilters({
  filters,
  onRemoveFilter,
  onClearAll,
}: {
  filters: Array<{ key: string; label: string; value: string }>;
  onRemoveFilter?: (key: string) => void;
  onClearAll?: () => void;
}) {
  if (filters.length === 0) {
    return null;
  }

  return (
    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
      {filters.map((filter) => (
        <Box
          key={filter.key}
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 1,
            px: 2,
            py: 0.5,
            backgroundColor: 'action.hover',
            borderRadius: 1,
            fontSize: '0.875rem',
          }}
        >
          <span>
            <strong>{filter.label}:</strong> {filter.value}
          </span>
          {onRemoveFilter && (
            <button
              onClick={() => onRemoveFilter(filter.key)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <XIcon className="size-3" />
            </button>
          )}
        </Box>
      ))}
      {onClearAll && (
        <Button
          variant="text"
          size="small"
          onClick={onClearAll}
          sx={{ ml: 'auto' }}
        >
          Clear All
        </Button>
      )}
    </Box>
  );
}
