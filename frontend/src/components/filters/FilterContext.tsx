/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, ReactNode, useCallback } from 'react';

export interface ActiveFilter {
  key: string;
  label: string;
  value: string;
}

export interface FilterState {
  search: string;
  filters: Record<string, any>;
  activeFilters: ActiveFilter[];
}

export interface FilterContextType {
  state: FilterState;
  setSearch: (search: string) => void;
  setFilter: (key: string, value: any, label?: string) => void;
  removeFilter: (key: string) => void;
  clearAllFilters: () => void;
  onFiltersChange?: () => void;
}

const FilterContext = createContext<FilterContextType | undefined>(undefined);

export interface FilterProviderProps {
  children: ReactNode;
  onFiltersChange?: () => void;
}

export function FilterProvider({ children, onFiltersChange }: FilterProviderProps) {
  const [state, setState] = useState<FilterState>({
    search: '',
    filters: {},
    activeFilters: [],
  });

  const setSearch = useCallback((search: string) => {
    setState((prev) => ({
      ...prev,
      search,
    }));
    onFiltersChange?.();
  }, [onFiltersChange]);

  const setFilter = useCallback((key: string, value: any, label?: string) => {
    setState((prev) => {
      const newFilters = { ...prev.filters };
      const newActiveFilters = [...prev.activeFilters];

      // Remove existing filter with same key
      const existingIndex = newActiveFilters.findIndex((f) => f.key === key);
      if (existingIndex > -1) {
        newActiveFilters.splice(existingIndex, 1);
      }

      if (value !== undefined && value !== null && value !== '') {
        newFilters[key] = value;
        // Use provided label or default to key
        const displayLabel = label || key;
        // Format the value for display
        const displayValue = Array.isArray(value) ? value.join(', ') : String(value);
        newActiveFilters.push({
          key,
          label: displayLabel,
          value: displayValue,
        });
      } else {
        // Remove filter if value is cleared
        delete newFilters[key];
      }

      return {
        ...prev,
        filters: newFilters,
        activeFilters: newActiveFilters,
      };
    });
    onFiltersChange?.();
  }, [onFiltersChange]);

  const removeFilter = useCallback((key: string) => {
    setState((prev) => {
      const newFilters = { ...prev.filters };
      const newActiveFilters = prev.activeFilters.filter((f) => f.key !== key);
      delete newFilters[key];

      return {
        ...prev,
        filters: newFilters,
        activeFilters: newActiveFilters,
      };
    });
    onFiltersChange?.();
  }, [onFiltersChange]);

  const clearAllFilters = useCallback(() => {
    setState({
      search: '',
      filters: {},
      activeFilters: [],
    });
    onFiltersChange?.();
  }, [onFiltersChange]);

  const value: FilterContextType = {
    state,
    setSearch,
    setFilter,
    removeFilter,
    clearAllFilters,
    onFiltersChange,
  };

  return (
    <FilterContext.Provider value={value}>
      {children}
    </FilterContext.Provider>
  );
}

export function useFilters(): FilterContextType {
  const context = useContext(FilterContext);
  if (!context) {
    throw new Error('useFilters must be used within a FilterProvider');
  }
  return context;
}
