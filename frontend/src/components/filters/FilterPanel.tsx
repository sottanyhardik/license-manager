import React, { ReactNode } from 'react';
import {
  Box,
  TextField,
  Button,
  Chip,
  Typography,
  Paper,
  InputAdornment,
} from '@mui/material';
import { Search, X } from 'lucide-react';
import { useFilters, FilterProvider, FilterProviderProps } from './FilterContext';

interface FilterPanelInnerProps {
  children: ReactNode;
}

/**
 * Inner component that uses the FilterContext
 */
function FilterPanelInner({ children }: FilterPanelInnerProps) {
  const { state, setSearch, removeFilter, clearAllFilters } = useFilters();
  const { search, activeFilters } = state;
  const hasActiveFilters = activeFilters.length > 0 || search.length > 0;

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 2,
        mb: 3,
      }}
    >
      {/* Main Filter Panel */}
      <Paper
        elevation={0}
        sx={{
          backgroundColor: 'background.paper',
          border: '1px solid',
          borderColor: 'divider',
          borderRadius: 1,
          overflow: 'hidden',
        }}
      >
        {/* Filter Controls Grid */}
        <Box
          sx={{
            p: { xs: 2, sm: 2.5, md: 3 },
            display: 'grid',
            gridTemplateColumns: {
              xs: '1fr',
              sm: 'repeat(2, 1fr)',
              md: 'repeat(3, 1fr)',
              lg: 'repeat(4, 1fr)',
            },
            gap: { xs: 2, sm: 2.5 },
            alignItems: 'start',
          }}
        >
          {children}
        </Box>
      </Paper>

      {/* Active Filters Display (Always Visible) */}
      {hasActiveFilters && (
        <Paper
          elevation={0}
          sx={{
            backgroundColor: 'background.paper',
            border: '1px solid',
            borderColor: 'divider',
            borderRadius: 1,
            p: { xs: 2, sm: 2.5, md: 3 },
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <Search size={16} style={{ color: 'var(--tb-text-secondary)' }} />
              Active Filters
            </Typography>
            <Button
              variant="text"
              size="small"
              onClick={clearAllFilters}
              startIcon={<X size={16} />}
              sx={{
                textTransform: 'none',
                color: 'error.main',
              }}
            >
              Clear All
            </Button>
          </Box>

          {/* Filter chips display */}
          <Box
            sx={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              alignItems: 'center',
            }}
          >
            {/* Search chip */}
            {search && (
              <Chip
                label={`Search: ${search}`}
                onDelete={() => setSearch('')}
                size="small"
                variant="outlined"
              />
            )}

            {/* Filter chips */}
            {activeFilters.map((filter) => (
              <Chip
                key={filter.key}
                label={`${filter.label}: ${filter.value}`}
                onDelete={() => removeFilter(filter.key)}
                size="small"
                variant="outlined"
              />
            ))}
          </Box>
        </Paper>
      )}
    </Box>
  );
}

export interface FilterPanelProps extends Omit<FilterProviderProps, 'children'> {
  children: ReactNode;
}

/**
 * FilterPanel Component
 *
 * Provides a complete filter interface with:
 * - Search field
 * - Filter controls (passed as children)
 * - Active filters display with individual removal
 * - Clear All button
 *
 * Usage:
 * ```tsx
 * <FilterPanel onFiltersChange={handleDataRefresh}>
 *   <FilterSelect label="Status" filterKey="status" options={[...]} />
 *   <FilterAutocomplete label="Port" filterKey="port" options={[...]} />
 * </FilterPanel>
 * ```
 */
export function FilterPanel({ children, onFiltersChange }: FilterPanelProps) {
  return (
    <FilterProvider onFiltersChange={onFiltersChange}>
      <FilterPanelInner>{children}</FilterPanelInner>
    </FilterProvider>
  );
}

// Backward compatibility exports for AdvancedFilter.tsx
export function FilterGrid({ children }: { children: ReactNode }) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: {
          xs: '1fr',
          sm: 'repeat(2, 1fr)',
          md: 'repeat(3, 1fr)',
          lg: 'repeat(4, 1fr)',
        },
        gap: { xs: 2, sm: 2.5 },
      }}
    >
      {children}
    </Box>
  );
}

export function FilterField({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  return (
    <Box
      sx={{
        gridColumn: wide ? { xs: 'span 1', sm: 'span 2', md: 'span 2', lg: 'span 2' } : 'auto',
        display: 'flex',
        flexDirection: 'column',
        gap: 0.75,
        minWidth: 0, // Prevent grid overflow
      }}
    >
      {children}
    </Box>
  );
}

export default FilterPanel;
