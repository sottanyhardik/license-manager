import * as React from "react";
import { Checkbox as MuiCheckbox, CheckboxProps as MuiCheckboxProps } from "@mui/material";

interface CheckboxProps extends Omit<MuiCheckboxProps, 'onChange'> {
    checked?: boolean | 'indeterminate';
    onCheckedChange?: (checked: boolean | 'indeterminate') => void;
    onChange?: (event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => void;
}

/**
 * Checkbox component wrapper around MUI Checkbox
 * Maps shadcn onCheckedChange to MUI onChange
 * Provides consistent checkbox styling across the application
 */
const Checkbox = React.forwardRef<HTMLButtonElement, CheckboxProps>(
    ({ className, checked, onCheckedChange, onChange, ...props }, ref) => {
        const handleChange = React.useCallback(
            (event: React.ChangeEvent<HTMLInputElement>, newChecked: boolean) => {
                if (onCheckedChange) {
                    onCheckedChange(newChecked);
                }
                if (onChange) {
                    onChange(event, newChecked);
                }
            },
            [onCheckedChange, onChange]
        );

        return (
            <MuiCheckbox
                ref={ref}
                checked={checked}
                onChange={handleChange}
                data-slot="checkbox"
                className={className}
                {...props}
            />
        );
    }
);

Checkbox.displayName = 'Checkbox';

export { Checkbox };
