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
    <Paper
      elevation={0}
      sx={{
        backgroundColor: 'background.paper',
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        p: 0,
        mb: 3,
      }}
    >
      {/* Search Field */}
      <Box sx={{ p: 2, borderBottom: '1px solid', borderColor: 'divider' }}>
        <TextField
          fullWidth
          placeholder="Search..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          slotProps={{
            input: {
              startAdornment: (
                <InputAdornment position="start">
                  <Search size={18} style={{ color: 'var(--mui-palette-action-disabled)' }} />
                </InputAdornment>
              ),
            },
          }}
          variant="outlined"
          size="small"
        />
      </Box>

      {/* Filter Controls */}
      <Box
        sx={{
          p: 2,
          borderBottom: hasActiveFilters ? '1px solid' : 'none',
          borderColor: 'divider',
          display: 'grid',
          gridTemplateColumns: {
            xs: '1fr',
            sm: 'repeat(2, 1fr)',
            md: 'repeat(3, 1fr)',
            lg: 'repeat(4, 1fr)',
          },
          gap: 2,
        }}
      >
        {children}
      </Box>

      {/* Active Filters Display */}
      {hasActiveFilters && (
        <Box sx={{ p: 2, backgroundColor: 'action.hover', borderRadius: 0 }}>
          <Typography
            variant="body2"
            sx={{
              fontWeight: 500,
              mb: 1,
              color: 'text.primary',
            }}
          >
            Active Filters:
          </Typography>
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

            {/* Clear All button */}
            {hasActiveFilters && (
              <Button
                variant="text"
                size="small"
                startIcon={<X size={16} />}
                onClick={clearAllFilters}
                sx={{
                  ml: 'auto',
                  textTransform: 'none',
                }}
              >
                Clear All
              </Button>
            )}
          </Box>
        </Box>
      )}
    </Paper>
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
        gap: 2,
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
        gridColumn: wide ? { sm: 'span 2', md: 'span 2', lg: 'span 2' } : 'auto',
      }}
    >
      {children}
    </Box>
  );
}

export default FilterPanel;
