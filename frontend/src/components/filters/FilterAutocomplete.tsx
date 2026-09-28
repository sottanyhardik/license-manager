import React from 'react';
import {
  Autocomplete,
  TextField,
  FormHelperText,
  Box,
} from '@mui/material';
import { useFilters } from './FilterContext';

export interface FilterAutocompleteOption {
  value: string | number;
  label: string;
}

export interface FilterAutocompleteProps {
  label: string;
  filterKey: string;
  options: FilterAutocompleteOption[];
  multiple?: boolean;
  searchable?: boolean;
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
  size?: 'small' | 'medium';
  gridSize?: 12 | 6 | 4 | 3;
  freeSolo?: boolean;
  loading?: boolean;
}

/**
 * FilterAutocomplete Component
 *
 * Searchable dropdown filter using MUI Autocomplete.
 *
 * Props:
 * - label: Display label for the filter
 * - filterKey: Unique key to store the filter value
 * - options: Array of {value, label} options
 * - multiple?: Support multiple selections (default: false)
 * - searchable?: Enable search functionality (default: true)
 * - helperText?: Optional helper text below the autocomplete
 * - required?: Mark as required (default: false)
 * - disabled?: Disable the autocomplete (default: false)
 * - size?: "small" or "medium" (default: "small")
 * - gridSize?: Responsive column size (default: 12)
 * - freeSolo?: Allow custom text input (default: false)
 * - loading?: Show loading state (default: false)
 *
 * Usage:
 * ```tsx
 * <FilterAutocomplete
 *   label="Port"
 *   filterKey="port"
 *   options={[
 *     { value: 'port1', label: 'Nhava Sheva' },
 *     { value: 'port2', label: 'Mundra' },
 *   ]}
 *   searchable={true}
 * />
 * ```
 */
export function FilterAutocomplete({
  label,
  filterKey,
  options,
  multiple = false,
  searchable = true,
  helperText,
  required = false,
  disabled = false,
  size = 'small',
  gridSize: _gridSize = 12,
  freeSolo = false,
  loading = false,
}: FilterAutocompleteProps) {
  const { state, setFilter } = useFilters();
  const value = state.filters[filterKey];

  // Normalize value to proper format for Autocomplete
  let displayValue: any = null;
  if (value !== undefined && value !== null) {
    if (multiple && Array.isArray(value)) {
      displayValue = options.filter((opt) => value.includes(opt.value));
    } else if (!multiple) {
      displayValue = options.find((opt) => opt.value === value) || null;
    }
  }

  const handleChange = (_event, newValue) => {
    if (multiple && Array.isArray(newValue)) {
      const values = newValue.map((v) => v.value);
      const labels = newValue.map((v) => v.label).join(', ');
      setFilter(filterKey, values, labels);
    } else if (!multiple && newValue) {
      setFilter(filterKey, newValue.value, newValue.label);
    } else {
      setFilter(filterKey, undefined);
    }
  };

  const handleInputChange = (_event, newInputValue, reason) => {
    // Handle free text input if freeSolo is enabled
    if (freeSolo && reason === 'input' && newInputValue) {
      // For free solo, we can set the value directly
      if (multiple) {
        const currentValues = state.filters[filterKey] || [];
        if (!currentValues.includes(newInputValue)) {
          setFilter(filterKey, [...currentValues, newInputValue], newInputValue);
        }
      }
    }
  };

  return (
    <Box
      sx={{
        width: '100%',
      }}
    >
        <Autocomplete
          options={options}
          getOptionLabel={(option) => option.label}
          isOptionEqualToValue={(option, val) => option.value === val?.value}
          value={displayValue}
          onChange={handleChange}
          onInputChange={handleInputChange}
          multiple={multiple}
          disabled={disabled || loading}
          freeSolo={freeSolo}
          loading={loading}
          slotProps={{
            paper: {
              sx: {
                '& .MuiAutocomplete-listbox': {
                  maxHeight: '200px',
                },
              },
            },
          }}
          renderInput={(params) => (
            <TextField
              {...params}
              label={label}
              required={required}
              size={size}
              variant="outlined"
              placeholder={searchable ? 'Search...' : undefined}
            />
          )}
        />
        {helperText && (
          <FormHelperText sx={{ mt: 0.5 }}>
            {helperText}
          </FormHelperText>
        )}
    </Box>
  );
}

export default FilterAutocomplete;
