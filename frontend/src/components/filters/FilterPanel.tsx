import React, { ReactNode, useState } from 'react';
import {
  Box,
  Button,
  Chip,
  Typography,
  Paper,
  useTheme as useMuiTheme,
} from '@mui/material';
import { Search, X, ChevronDown } from 'lucide-react';
import { useFilters, FilterProvider, FilterProviderProps } from './FilterContext';

interface FilterPanelInnerProps {
  children: ReactNode;
  collapsible?: boolean;
}

/**
 * Inner component that uses the FilterContext
 */
function FilterPanelInner({ children, collapsible = false }: FilterPanelInnerProps) {
  const { state, setSearch, removeFilter, clearAllFilters } = useFilters();
  const { search, activeFilters } = state;
  const hasActiveFilters = activeFilters.length > 0 || search.length > 0;
  const [isExpanded, setIsExpanded] = useState(!collapsible);
  const muiTheme = useMuiTheme();

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        gap: 1.5,
        mb: 3,
        width: '100%',
      }}
    >
      {/* Main Filter Panel - MUI Minimal Dashboard Style */}
      <Paper
        elevation={0}
        sx={{
          backgroundColor: 'background.paper',
          border: `1px solid ${muiTheme.palette.divider}`,
          borderRadius: 0.75,
          overflow: 'hidden',
          width: '100%',
          transition: 'all 0.2s ease',
        }}
      >
        {/* Collapsible Header */}
        {collapsible && (
          <Box
            sx={{
              px: { xs: 2, sm: 2, md: 2.5 },
              py: 1,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: !isExpanded && hasActiveFilters ? `1px solid ${muiTheme.palette.divider}` : 'none',
              cursor: 'pointer',
              userSelect: 'none',
              transition: 'background-color 0.2s ease',
              '&:hover': {
                backgroundColor: muiTheme.palette.action.hover,
              },
            }}
            onClick={() => setIsExpanded(!isExpanded)}
          >
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                fontSize: '0.875rem',
              }}
            >
              <Search size={16} />
              Filters
            </Typography>
            <ChevronDown
              size={16}
              style={{
                transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                transition: 'transform 200ms cubic-bezier(0.4, 0, 0.2, 1)',
              }}
            />
          </Box>
        )}

        {/* Filter Controls Grid - Visible when expanded */}
        {isExpanded && (
          <Box
            sx={{
              p: { xs: 2, sm: 2, md: 2.5 },
              display: 'grid',
              gridTemplateColumns: {
                xs: '1fr',
                sm: 'repeat(2, 1fr)',
                md: 'repeat(3, 1fr)',
                lg: 'repeat(4, 1fr)',
                xl: 'repeat(5, 1fr)',
              },
              gap: { xs: 1.5, sm: 2, md: 2 },
              alignItems: 'start',
            }}
          >
            {children}
          </Box>
        )}

        {/* Collapsed state - show active filters in panel */}
        {!isExpanded && hasActiveFilters && (
          <Box
            sx={{
              px: { xs: 2, sm: 2.5, md: 3 },
              py: 2,
              display: 'flex',
              flexWrap: 'wrap',
              gap: 1,
              alignItems: 'center',
            }}
          >
            {search && (
              <Chip
                label={`Search: ${search}`}
                onDelete={() => setSearch('')}
                size="small"
                variant="outlined"
              />
            )}
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
        )}
      </Paper>

      {/* Active Filters Display - Separate panel when not collapsed */}
      {!collapsible && hasActiveFilters && (
        <Paper
          elevation={0}
          sx={{
            backgroundColor: 'background.paper',
            border: `1px solid ${muiTheme.palette.divider}`,
            borderRadius: 0.75,
            p: { xs: 2, sm: 2, md: 2.5 },
            width: '100%',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography
              variant="body2"
              sx={{
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 1,
              }}
            >
              <Search size={16} style={{ color: muiTheme.palette.text.secondary }} />
              Active Filters
            </Typography>
            <Button
              variant="text"
              size="small"
              onClick={clearAllFilters}
              startIcon={<X size={16} />}
              sx={{
                textTransform: 'none',
                fontSize: '0.85rem',
                fontWeight: 600,
                color: 'error.main',
                '&:hover': {
                  backgroundColor: 'transparent',
                },
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

      {/* Collapsed with active filters - show clear all */}
      {collapsible && !isExpanded && hasActiveFilters && (
        <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
          <Button
            variant="text"
            size="small"
            onClick={clearAllFilters}
            startIcon={<X size={16} />}
            sx={{
              textTransform: 'none',
              fontSize: '0.85rem',
              fontWeight: 600,
              color: 'error.main',
            }}
          >
            Clear All
          </Button>
        </Box>
      )}
    </Box>
  );
}

export interface FilterPanelProps extends Omit<FilterProviderProps, 'children'> {
  children: ReactNode;
  collapsible?: boolean;
}

/**
 * FilterPanel Component
 *
 * Provides a complete filter interface with:
 * - Professional surface with subtle border
 * - Responsive CSS Grid (4 cols at 1536px, 3 at 1200px, 2 at 768px, 1 at 375px)
 * - Active filters display with individual removal and Clear All button
 * - Optional collapsible design
 * - All controls 40-44px height
 *
 * Usage:
 * ```tsx
 * <FilterPanel onFiltersChange={handleDataRefresh} collapsible>
 *   <FilterSelect label="Status" filterKey="status" options={[...]} />
 *   <FilterAutocomplete label="Port" filterKey="port" options={[...]} />
 * </FilterPanel>
 * ```
 */
export function FilterPanel({ children, onFiltersChange, collapsible = false }: FilterPanelProps) {
  return (
    <FilterProvider onFiltersChange={onFiltersChange}>
      <FilterPanelInner collapsible={collapsible}>{children}</FilterPanelInner>
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
          xl: 'repeat(5, 1fr)',
        },
        gap: { xs: 1.5, sm: 2, md: 2 },
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
        gridColumn: wide ? { xs: 'span 1', sm: 'span 2', md: 'span 2', lg: 'span 2', xl: 'span 2' } : { xs: 'span 1', sm: 'span 1', md: 'span 1', lg: 'span 1', xl: 'span 1' },
        display: 'flex',
        flexDirection: 'column',
        gap: 0.75,
        minWidth: 0,
        width: '100%',
      }}
    >
      {children}
    </Box>
  );
}

export default FilterPanel;
