import React from 'react';
import {
  Grid,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  FormHelperText,
} from '@mui/material';
import { useFilters } from './FilterContext';

export interface FilterSelectOption {
  value: string | number;
  label: string;
}

export interface FilterSelectProps {
  label: string;
  filterKey: string;
  options: FilterSelectOption[];
  multiple?: boolean;
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
  size?: 'small' | 'medium';
  gridSize?: 12 | 6 | 4 | 3;
}

/**
 * FilterSelect Component
 *
 * Static dropdown filter using MUI Select.
 *
 * Props:
 * - label: Display label for the filter
 * - filterKey: Unique key to store the filter value
 * - options: Array of {value, label} options
 * - multiple?: Support multiple selections (default: false)
 * - helperText?: Optional helper text below the select
 * - required?: Mark as required (default: false)
 * - disabled?: Disable the select (default: false)
 * - size?: "small" or "medium" (default: "small")
 * - gridSize?: Responsive column size (default: 12)
 *
 * Usage:
 * ```tsx
 * <FilterSelect
 *   label="Status"
 *   filterKey="status"
 *   options={[
 *     { value: 'active', label: 'Active' },
 *     { value: 'inactive', label: 'Inactive' },
 *   ]}
 * />
 * ```
 */
export function FilterSelect({
  label,
  filterKey,
  options,
  multiple = false,
  helperText,
  required = false,
  disabled = false,
  size = 'small',
  gridSize = 12,
}: FilterSelectProps) {
  const { state, setFilter } = useFilters();
  const value = state.filters[filterKey] ?? (multiple ? [] : '');

  const handleChange = (event) => {
    const newValue = event.target.value;
    // Pass both the value and the label for display
    const selectedOption = options.find((opt) => opt.value === newValue);
    const displayLabel = selectedOption?.label || label;
    setFilter(filterKey, newValue, displayLabel);
  };

  return (
    <Grid item xs={12} sm={gridSize === 12 ? 12 : 6} md={gridSize === 12 ? 12 : gridSize === 6 ? 6 : 4} lg={gridSize} component="div">
      <FormControl
        fullWidth
        size={size}
        variant="outlined"
        required={required}
        disabled={disabled}
        error={required && !value}
      >
        <InputLabel>{label}</InputLabel>
        <Select
          value={value}
          onChange={handleChange}
          label={label}
          multiple={multiple}
        >
          <MenuItem value="">
            <em>None</em>
          </MenuItem>
          {options.map((option) => (
            <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
        </Select>
        {helperText && <FormHelperText>{helperText}</FormHelperText>}
      </FormControl>
    </Grid>
  );
}

export default FilterSelect;
