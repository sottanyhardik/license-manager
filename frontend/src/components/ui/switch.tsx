import * as React from "react";
import { Switch as MuiSwitch, SwitchProps as MuiSwitchProps } from "@mui/material";

interface SwitchProps extends Omit<MuiSwitchProps, 'onChange'> {
    checked?: boolean;
    onCheckedChange?: (checked: boolean) => void;
    onChange?: (event: React.ChangeEvent<HTMLInputElement>, checked: boolean) => void;
}

/**
 * Switch component wrapper around MUI Switch
 * Maps shadcn onCheckedChange to MUI onChange
 * Provides consistent switch/toggle styling across the application
 */
const Switch = React.forwardRef<HTMLButtonElement, SwitchProps>(
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
            <MuiSwitch
                ref={ref}
                checked={checked}
                onChange={handleChange}
                data-slot="switch"
                className={className}
                {...props}
            />
        );
    }
);

Switch.displayName = 'Switch';

export { Switch };
