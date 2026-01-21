# Back Button & Filter Persistence Implementation

## Overview
This application implements comprehensive back button support with automatic filter/pagination preservation across all pages. Users can navigate freely between pages and always return to their previous state.

## Key Features

### 1. **Filter Persistence**
- Filters, pagination, and search state are automatically saved when navigating away
- State is restored when returning to list pages
- State expires after 1 hour to prevent stale data

### 2. **Browser Back Button Support**
- Browser back/forward buttons work seamlessly
- Filters are preserved when using browser navigation
- Works across all major pages

### 3. **Consistent Navigation**
- All "Back" and "Cancel" buttons use the same navigation utilities
- Predictable behavior across the entire application

## Implementation Details

### Utilities

#### `navigationUtils.js`
Location: `/utils/navigationUtils.js`

Key Functions:
- `navigateToList(navigate, entityName, options)` - Navigate to list with filter preservation
- `navigateToEdit(navigate, entityName, id, currentFilters)` - Navigate to edit page
- `navigateToCreate(navigate, entityName, currentFilters)` - Navigate to create page
- `shouldRestoreListFilters(entityName)` - Check if filters should be restored
- `getStoredFilters(entityName)` - Retrieve stored filters
- `clearStoredFilters(entityName)` - Clear stored filters
- `navigateBack(navigate)` - Navigate back with browser history support

#### `filterPersistence.js`
Location: `/utils/filterPersistence.js`

Key Functions:
- `saveFilterState(pageKey, { filters, pagination, search })` - Save filter state
- `restoreFilterState(pageKey)` - Restore filter state
- `clearFilterState(pageKey)` - Clear filter state
- `shouldRestoreFilters()` - Check if filters should be restored
- `markNewItemCreated(itemId)` - Mark newly created items
- `getNewlyCreatedItem()` - Get newly created item ID

### Custom Hooks

#### `useBackButton`
Location: `/hooks/useBackButton.js`

Usage:
```javascript
import { useBackButton } from '../hooks/useBackButton';

// In your component
useBackButton('entityName', enabled);
```

Features:
- Automatically handles browser back button
- Preserves filter state on back navigation
- Can be disabled for modal views

## Pages with Full Support

### ✅ Masters (All Entities)
- **List Pages**: `/masters/{entity}`, `/licenses`, `/allotments`, `/trades`, `/bill-of-entries`
  - Filter state saved on navigation
  - Restored when returning from edit/create
  - Browser back button supported

- **Form Pages**: Create/Edit pages
  - Back button navigates to list with filters
  - Browser back button supported
  - Cancel button uses `navigateToList()`

### ✅ Allotments
- **AllotmentAction** (`/allotments/{id}/allocate`)
  - Back to Allotments button
  - Browser back button supported
  - Filter preservation enabled

### ✅ Trades
- **TradeForm** (`/trades/create`, `/trades/{id}/edit`)
  - Back to Trades button
  - Browser back button supported
  - Filter preservation enabled

### ✅ Reports
- Item Pivot Report
- Item Report
- License Ledger

## Usage Examples

### In a List Page
```javascript
import { saveFilterState, restoreFilterState, shouldRestoreFilters } from '../../utils/filterPersistence';

export default function MasterList({ entityName }) {
    const [filters, setFilters] = useState({});

    // Restore filters on mount
    useEffect(() => {
        const shouldRestore = shouldRestoreFilters();
        const restored = shouldRestore ? restoreFilterState(entityName) : null;

        if (restored) {
            setFilters(restored.filters || {});
            setPagination(restored.pagination || {});
        }
    }, []);

    // Save filters when navigating away
    const handleEdit = (id) => {
        saveFilterState(entityName, {
            filters,
            pagination,
            search
        });
        navigate(`/masters/${entityName}/${id}/edit`);
    };

    return (
        // ... list UI
    );
}
```

### In a Form Page
```javascript
import { navigateToList } from '../../utils/navigationUtils';
import { useBackButton } from '../../hooks/useBackButton';

export default function MasterForm({ entityName }) {
    const navigate = useNavigate();

    // Enable browser back button support
    useBackButton(entityName);

    const handleCancel = () => {
        // Navigate back with filter preservation
        navigateToList(navigate, entityName, { preserveFilters: true });
    };

    return (
        <form>
            {/* ... form fields */}
            <button type="button" onClick={handleCancel}>
                <i className="bi bi-arrow-left me-2"></i>
                Back to List
            </button>
        </form>
    );
}
```

### In a Detail Page
```javascript
import { navigateToList } from '../../utils/navigationUtils';
import { useBackButton } from '../../hooks/useBackButton';

export default function DetailPage({ entityName }) {
    const navigate = useNavigate();

    // Enable browser back button support
    useBackButton(entityName);

    return (
        <div>
            {/* ... detail view */}
            <button onClick={() => navigateToList(navigate, entityName, { preserveFilters: true })}>
                <i className="bi bi-arrow-left me-1"></i>
                Back to List
            </button>
        </div>
    );
}
```

## Storage Keys

Filter states are stored in `sessionStorage` with the following key patterns:

- Filter state: `filterState_{entityName}`
- Navigation flags: `{entityName}ListFilters`
- Newly created items: `newlyCreatedItem`

## Browser Compatibility

Works in all modern browsers that support:
- `sessionStorage`
- `popstate` event
- React Router v6+

## Best Practices

1. **Always use navigation utilities** instead of direct `navigate()` calls
2. **Enable browser back button support** in all form/detail pages using `useBackButton()`
3. **Save filter state** before navigating away from list pages
4. **Check for restoration** when mounting list pages
5. **Use consistent button text** ("Back to List", "Back to {Entity}") with arrow icon

## Troubleshooting

### Filters not restoring
- Check if `shouldRestoreFilters()` is called on mount
- Verify filter state is saved before navigation
- Check browser console for storage errors

### Browser back button not working
- Ensure `useBackButton()` hook is used
- Check if `popstate` event listeners are registered
- Verify sessionStorage is not disabled

### Stale filter state
- Filter states expire after 1 hour automatically
- Clear manually using `clearStoredFilters(entityName)`

## Future Enhancements

- [ ] Add filter state to URL query parameters for shareable links
- [ ] Implement filter presets/favorites
- [ ] Add "Clear All Filters" button with confirmation
- [ ] Persist scroll position on list pages
- [ ] Add filter history (undo/redo filters)
