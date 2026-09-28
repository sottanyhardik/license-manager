import React from 'react';
import {
  Grid,
  TextField,
  Box,
  FormHelperText,
} from '@mui/material';
import { useFilters } from './FilterContext';

export interface FilterDateRangeProps {
  label: string;
  filterKey: string;
  helperText?: string;
  required?: boolean;
  disabled?: boolean;
  size?: 'small' | 'medium';
  gridSize?: 12 | 6 | 4 | 3;
  minDate?: string;
  maxDate?: string;
}

/**
 * FilterDateRange Component
 *
 * Date range filter using MUI TextField with type="date".
 *
 * Props:
 * - label: Display label for the filter
 * - filterKey: Unique key to store the filter value
 * - helperText?: Optional helper text below the date field
 * - required?: Mark as required (default: false)
 * - disabled?: Disable the date field (default: false)
 * - size?: "small" or "medium" (default: "small")
 * - gridSize?: Responsive column size (default: 12)
 * - minDate?: Minimum selectable date (format: YYYY-MM-DD)
 * - maxDate?: Maximum selectable date (format: YYYY-MM-DD)
 *
 * Note: The filter stores both startDate and endDate in the filters object.
 * For a single date filter, use filterKey like "startDate" and create separate instances.
 *
 * Usage:
 * ```tsx
 * <FilterDateRange
 *   label="From Date"
 *   filterKey="startDate"
 * />
 * <FilterDateRange
 *   label="To Date"
 *   filterKey="endDate"
 * />
 * ```
 */
export function FilterDateRange({
  label,
  filterKey,
  helperText,
  required = false,
  disabled = false,
  size = 'small',
  gridSize = 12,
  minDate,
  maxDate,
}: FilterDateRangeProps) {
  const { state, setFilter } = useFilters();
  const value = state.filters[filterKey] || '';

  const handleChange = (event) => {
    const newValue = event.target.value;
    if (newValue) {
      setFilter(filterKey, newValue, label);
    } else {
      setFilter(filterKey, undefined);
    }
  };

  return (
    <Grid item xs={12} sm={gridSize === 12 ? 12 : 6} md={gridSize === 12 ? 12 : gridSize === 6 ? 6 : 4} lg={gridSize} component="div">
      <Box>
        <TextField
          fullWidth
          type="date"
          label={label}
          value={value}
          onChange={handleChange}
          disabled={disabled}
          required={required}
          size={size}
          variant="outlined"
          slotProps={{
            inputLabel: {
              shrink: true,
            },
            input: {
              min: minDate,
              max: maxDate,
            },
          }}
        />
        {helperText && (
          <FormHelperText sx={{ mt: 0.5 }}>
            {helperText}
          </FormHelperText>
        )}
      </Box>
    </Grid>
  );
}

export default FilterDateRange;
