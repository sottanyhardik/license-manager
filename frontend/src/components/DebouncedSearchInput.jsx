/**
 * Debounced Search Input Component
 *
 * A text input that debounces changes to reduce API calls while typing.
 * Shows a loading indicator during the debounce period.
 *
 * @param {string} value - Current search value
 * @param {function} onChange - Callback when debounced value changes
 * @param {number} delay - Debounce delay in milliseconds (default: 500)
 * @param {string} placeholder - Input placeholder text
 * @param {string} className - Additional CSS classes
 * @param {object} style - Inline styles
 *
 * @example
 * <DebouncedSearchInput
 *   value={searchTerm}
 *   onChange={setSearchTerm}
 *   delay={500}
 *   placeholder="Search licenses..."
 * />
 */

import React, { useState, useEffect, useRef } from 'react';
import { useDebouncedState } from '../hooks/useDebounce';

export default function DebouncedSearchInput({
    value,
    onChange,
    delay = 500,
    placeholder = "Search...",
    className = "form-control",
    style = {},
    showPendingIndicator = true,
    icon = "bi-search"
}) {
    const [localValue, setLocalValue] = useState(value);
    const { debouncedValue, isPending } = useDebouncedState(localValue, delay);

    const valueRef = useRef(value);
    const onChangeRef = useRef(onChange);
    useEffect(() => {
        valueRef.current = value;
        onChangeRef.current = onChange;
    });

    useEffect(() => {
        setLocalValue(value);
    }, [value]);

    useEffect(() => {
        if (debouncedValue !== valueRef.current) {
            onChangeRef.current(debouncedValue);
        }
    }, [debouncedValue]);

    const handleChange = (e) => {
        setLocalValue(e.target.value);
    };

    const handleClear = () => {
        setLocalValue('');
        onChange('');
    };

    return (
        <div className="position-relative">
            <div className="input-group">
                <span className="input-group-text bg-white border-end-0">
                    <i className={`bi ${icon}`}></i>
                </span>
                <input
                    type="text"
                    className={`${className} border-start-0 ps-0`}
                    placeholder={placeholder}
                    value={localValue}
                    onChange={handleChange}
                    style={style}
                />
                {localValue && (
                    <button
                        className="btn btn-sm border-0 position-absolute end-0 top-50 translate-middle-y"
                        onClick={handleClear}
                        style={{ zIndex: 10, marginRight: '8px' }}
                        type="button"
                    >
                        <i className="bi bi-x-circle" style={{ color: 'var(--bs-gray-500)' }}></i>
                    </button>
                )}
            </div>

            {/* Debounce pending indicator */}
            {showPendingIndicator && isPending && (
                <div
                    className="position-absolute end-0 top-50 translate-middle-y me-5"
                    style={{ pointerEvents: 'none' }}
                >
                    <span className="spinner-border spinner-border-sm text-primary" role="status">
                        <span className="visually-hidden">Searching...</span>
                    </span>
                </div>
            )}
        </div>
    );
}
