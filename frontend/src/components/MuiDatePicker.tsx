import React from 'react';
import {
  TextField,
  TextFieldProps,
  Box,
  FormHelperText,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import dayjs, { Dayjs } from 'dayjs';

/**
 * MuiDatePicker Component
 *
 * Standardized date picker across the application using MUI X DatePicker.
 * Wraps the MUI DatePicker with consistent styling and behavior.
 *
 * Props:
 * - label: Display label
 * - value: Date value (string YYYY-MM-DD or Date or Dayjs or null)
 * - onChange: Callback when date changes (returns Dayjs or null)
 * - disabled?: Whether the field is disabled
 * - required?: Whether the field is required
 * - helperText?: Helper text below the field
 * - error?: Whether the field has an error
 * - size?: "small" or "medium" (default: "small")
 * - minDate?: Minimum selectable date
 * - maxDate?: Maximum selectable date
 * - fullWidth?: Whether to take full width (default: true)
 * - slotProps?: Additional MUI slot props
 */

interface MuiDatePickerProps {
  label?: string;
  value?: string | Date | Dayjs | null;
  onChange?: (date: Dayjs | null) => void;
  disabled?: boolean;
  required?: boolean;
  helperText?: string;
  error?: boolean;
  size?: 'small' | 'medium';
  minDate?: string | Date | Dayjs;
  maxDate?: string | Date | Dayjs;
  fullWidth?: boolean;
  slotProps?: any;
  textFieldProps?: TextFieldProps;
  [key: string]: any;
}

export const MuiDatePicker = React.forwardRef<HTMLDivElement, MuiDatePickerProps>(
  (
    {
      value,
      onChange,
      label,
      disabled = false,
      required = false,
      helperText,
      error = false,
      size = 'small',
      minDate,
      maxDate,
      fullWidth = true,
      slotProps,
      textFieldProps,
      ...props
    },
    ref
  ) => {
    // Convert string/Date to Dayjs
    const convertValue = (val: string | Date | Dayjs | null | undefined): Dayjs | null => {
      if (!val) return null;
      if (dayjs.isDayjs(val)) return val;
      if (val instanceof Date) return dayjs(val);
      if (typeof val === 'string') {
        const parsed = dayjs(val);
        if (parsed.isValid()) return parsed;
      }
      return null;
    };

    const dayjsValue = convertValue(value);

    const handleChange = (date: Dayjs | null) => {
      onChange?.(date);
    };

    return (
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <Box ref={ref} sx={{ width: fullWidth ? '100%' : 'auto' }}>
          <DatePicker
            {...props}
            label={label}
            value={dayjsValue}
            onChange={handleChange}
            disabled={disabled}
            minDate={minDate ? dayjs(minDate) : undefined}
            maxDate={maxDate ? dayjs(maxDate) : undefined}
            slotProps={{
              ...slotProps,
              textField: {
                size: size as 'small' | 'medium',
                fullWidth,
                error,
                required,
                variant: 'outlined',
                ...textFieldProps,
              },
            }}
          />
          {helperText && (
            <FormHelperText sx={{ mt: 0.5 }} error={error}>
              {helperText}
            </FormHelperText>
          )}
        </Box>
      </LocalizationProvider>
    );
  }
);

MuiDatePicker.displayName = 'MuiDatePicker';

export default MuiDatePicker;
