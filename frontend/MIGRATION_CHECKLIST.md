# Frontend Components Migration Checklist

This checklist helps migrate existing components to use the new common components and hooks.

## Overview

The new common components library provides:
- **useFormState** - Form state management
- **useApiRequest** - API request handling
- **LoadingSpinner** - Loading indicators
- **ErrorAlert** - Error/success messages
- **FormField** - Form inputs with validation
- **Modal** - Modal dialogs

## Pre-Migration Steps

- [ ] Read `/frontend/src/components/common/README.md`
- [ ] Review `/frontend/src/components/common/USAGE_EXAMPLES.md`
- [ ] Keep `/frontend/src/components/common/QUICK_REFERENCE.md` handy
- [ ] Backup current code or create a new branch
- [ ] Identify components to migrate first (start with simple ones)

---

## Migration Patterns

### Pattern 1: Migrate Form State Management

#### Before (Old Pattern)
```jsx
const [formData, setFormData] = useState({ name: '', email: '' });
const [errors, setErrors] = useState({});
const [loading, setLoading] = useState(false);

const handleChange = (e) => {
  const { name, value } = e.target;
  setFormData(prev => ({ ...prev, [name]: value }));
  // Clear error
  if (errors[name]) {
    setErrors(prev => {
      const next = { ...prev };
      delete next[name];
      return next;
    });
  }
};

const handleSubmit = async (e) => {
  e.preventDefault();
  setLoading(true);
  setErrors({});
  try {
    await api.post('/endpoint', formData);
    toast.success('Success!');
  } catch (err) {
    setErrors(err.response?.data || {});
    toast.error('Error!');
  } finally {
    setLoading(false);
  }
};
```

#### After (New Pattern)
```jsx
import { useFormState } from '@/hooks';

const { formData, errors, loading, handleChange, handleSubmit } = useFormState(
  { name: '', email: '' },
  {
    endpoint: '/endpoint',
    method: 'post',
    successMessage: 'Success!',
    errorMessage: 'Error!'
  }
);
```

**Checklist for this pattern:**
- [ ] Replace state declarations with `useFormState`
- [ ] Remove manual `handleChange` implementation
- [ ] Remove manual `handleSubmit` implementation
- [ ] Remove manual error clearing logic
- [ ] Remove toast notifications (now automatic)
- [ ] Test form submission
- [ ] Test validation

---

### Pattern 2: Migrate API Calls

#### Before (Old Pattern)
```jsx
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);
const [data, setData] = useState(null);

const fetchData = async () => {
  setLoading(true);
  setError(null);
  try {
    const response = await api.get('/data');
    setData(response.data);
    toast.success('Data loaded');
  } catch (err) {
    const msg = err.response?.data?.detail || 'Error loading data';
    setError(msg);
    toast.error(msg);
  } finally {
    setLoading(false);
  }
};

useEffect(() => {
  fetchData();
}, []);
```

#### After (New Pattern)
```jsx
import { useApiRequest } from '@/hooks';

const { get, loading, error, data } = useApiRequest({
  showSuccessToast: true,
  successMessage: 'Data loaded',
  retry: 3,
  cache: true
});

useEffect(() => {
  get('/data');
}, []);
```

**Checklist for this pattern:**
- [ ] Replace state declarations with `useApiRequest`
- [ ] Replace fetch function with `get`, `post`, etc.
- [ ] Remove manual loading state management
- [ ] Remove manual error handling
- [ ] Remove toast notifications
- [ ] Add retry and cache if needed
- [ ] Test API calls
- [ ] Test error handling

---

### Pattern 3: Migrate Loading Indicators

#### Before (Old Pattern)
```jsx
{loading && (
  <div className="text-center">
    <div className="spinner-border" role="status">
      <span className="visually-hidden">Loading...</span>
    </div>
  </div>
)}
```

#### After (New Pattern)
```jsx
import { LoadingSpinner } from '@/components/common';

{loading && <LoadingSpinner text="Loading..." />}
```

**Checklist for this pattern:**
- [ ] Replace manual spinner markup with `LoadingSpinner`
- [ ] Choose appropriate size (`sm`, `md`, `lg`, `xl`)
- [ ] Choose appropriate variant (`spinner`, `dots`, `bars`, `grow`)
- [ ] Add text if needed
- [ ] Use `overlay` prop for blocking UI
- [ ] Test loading states

---

### Pattern 4: Migrate Error Displays

#### Before (Old Pattern)
```jsx
{error && (
  <div className="alert alert-danger" role="alert">
    <strong>Error:</strong> {error}
  </div>
)}
```

#### After (New Pattern)
```jsx
import { ErrorAlert } from '@/components/common';

{error && <ErrorAlert severity="error" message={error} />}
```

**Checklist for this pattern:**
- [ ] Replace manual alert markup with `ErrorAlert`
- [ ] Choose severity (`error`, `warning`, `info`, `success`)
- [ ] Add title if needed
- [ ] Add dismissible if needed
- [ ] Use `ValidationErrors` for form errors
- [ ] Use `ApiError` for API errors
- [ ] Test error display

---

### Pattern 5: Migrate Form Fields

#### Before (Old Pattern)
```jsx
<div className="col-md-6">
  <label className="form-label fw-bold">
    Email {required && '*'}
  </label>
  <input
    type="email"
    name="email"
    className={`form-control ${errors.email ? 'is-invalid' : ''}`}
    value={formData.email}
    onChange={handleChange}
  />
  {errors.email && (
    <div className="invalid-feedback">{errors.email}</div>
  )}
</div>
```

#### After (New Pattern)
```jsx
import { FormField } from '@/components/common';

<FormField
  label="Email"
  name="email"
  type="email"
  value={formData.email}
  onChange={handleChange}
  error={errors.email}
  required
/>
```

**Checklist for this pattern:**
- [ ] Replace manual field markup with `FormField`
- [ ] Remove manual error class logic
- [ ] Remove manual error display
- [ ] Add `helpText` if needed
- [ ] Use `FormSelect` for dropdowns
- [ ] Use `FormTextArea` for text areas
- [ ] Use `FormCheckbox` for checkboxes
- [ ] Test field rendering
- [ ] Test validation display

---

### Pattern 6: Migrate Modals

#### Before (Old Pattern)
```jsx
{show && (
  <div className="modal show d-block" style={{ backgroundColor: 'rgba(0,0,0,0.5)' }}>
    <div className="modal-dialog modal-xl">
      <div className="modal-content">
        <div className="modal-header">
          <h5 className="modal-title">Title</h5>
          <button className="btn-close" onClick={onHide} />
        </div>
        <div className="modal-body">
          {children}
        </div>
        <div className="modal-footer">
          <button onClick={onHide}>Close</button>
          <button onClick={handleSave}>Save</button>
        </div>
      </div>
    </div>
  </div>
)}
```

#### After (New Pattern)
```jsx
import { Modal } from '@/components/common';

<Modal
  show={show}
  onHide={onHide}
  title="Title"
  size="xl"
  footer={
    <>
      <button onClick={onHide}>Close</button>
      <button onClick={handleSave}>Save</button>
    </>
  }
>
  {children}
</Modal>
```

**Checklist for this pattern:**
- [ ] Replace manual modal markup with `Modal`
- [ ] Move footer buttons to `footer` prop
- [ ] Add `centered` if needed
- [ ] Add `scrollable` if needed
- [ ] Use `ConfirmModal` for confirmations
- [ ] Use `AlertModal` for alerts
- [ ] Test modal opening/closing
- [ ] Test keyboard navigation (ESC)
- [ ] Test backdrop click

---

## Component-Specific Migration

### Priority 1: High-Impact Components (Migrate First)

#### Forms
- [ ] `/pages/LicensePage.jsx`
- [ ] `/pages/TradeForm.jsx`
- [ ] `/pages/masters/*` (all master forms)
- [ ] `/components/AllotmentFormModal.jsx`
- [ ] `/components/MasterFormModal.jsx`
- [ ] `/components/TransferLetterForm.jsx`

**Expected Impact:** ~500 lines reduced

#### API Calls
- [ ] `/pages/Dashboard.jsx`
- [ ] `/pages/LicenseLedger.jsx`
- [ ] `/pages/LicenseLedgerDetail.jsx`
- [ ] `/pages/reports/*` (all report pages)

**Expected Impact:** ~800 lines reduced

### Priority 2: Medium-Impact Components

#### Loading States
- [ ] All pages with data fetching
- [ ] All forms with submission states
- [ ] All modals with async operations

**Expected Impact:** ~200 lines reduced

#### Error Displays
- [ ] All pages with error handling
- [ ] All forms with validation
- [ ] All API call sites

**Expected Impact:** ~300 lines reduced

### Priority 3: Low-Impact Components (Nice to Have)

- [ ] Existing form fields that work fine
- [ ] Simple modals with no complex behavior
- [ ] Static content pages

---

## Testing Checklist

After migrating each component:

### Functionality
- [ ] Component renders correctly
- [ ] All features work as before
- [ ] Form validation works
- [ ] API calls succeed
- [ ] Error handling works
- [ ] Loading states display
- [ ] Success messages show

### User Experience
- [ ] UI looks consistent with design
- [ ] Animations are smooth
- [ ] No layout shifts
- [ ] Responsive on mobile
- [ ] Keyboard navigation works

### Accessibility
- [ ] Screen reader announces changes
- [ ] Focus management works
- [ ] ARIA labels present
- [ ] Keyboard shortcuts work
- [ ] Color contrast sufficient

### Performance
- [ ] No unnecessary re-renders
- [ ] API requests cached if appropriate
- [ ] Loading indicators show immediately
- [ ] No console errors or warnings

---

## Common Pitfalls

### 1. Event Handlers

**Problem:** `handleChange` signature changed
```jsx
// Old
const handleChange = (field, value) => { ... }
onChange={(e) => handleChange('email', e.target.value)}

// New
const { handleChange } = useFormState(...)
onChange={handleChange}  // Directly pass the handler
```

**Solution:** Use the `handleChange` from hook directly, or use `setFieldValue` for programmatic updates.

### 2. Validation Timing

**Problem:** Validation not running when expected

**Solution:**
```jsx
useFormState(initialData, {
  validateOnChange: false,  // Validate on submit only
  validateOnBlur: true      // Validate when field loses focus
})
```

### 3. API Request Caching

**Problem:** Stale data from cache

**Solution:**
```jsx
// Clear cache when needed
clearCache('user-123');

// Skip cache for specific request
get('/users', params, { skipCache: true });
```

### 4. Modal Focus Issues

**Problem:** Focus not returning after modal close

**Solution:**
```jsx
<Modal
  restoreFocus={true}  // Restore focus on close
  autoFocus={true}     // Auto focus on open
/>
```

### 5. Form Reset Issues

**Problem:** Form not resetting after submission

**Solution:**
```jsx
const { resetForm } = useFormState(...);

const onSubmit = async (values) => {
  await api.post('/endpoint', values);
  resetForm();  // Reset after success
};
```

---

## Rollback Plan

If migration causes issues:

1. **Immediate Rollback**
   ```bash
   git checkout HEAD -- path/to/component.jsx
   ```

2. **Keep Old and New Side by Side**
   - Rename old component to `ComponentName.old.jsx`
   - Create new component with common components
   - Compare behavior
   - Remove old when confident

3. **Feature Flag**
   ```jsx
   const USE_NEW_COMPONENTS = false;

   return USE_NEW_COMPONENTS ? <NewComponent /> : <OldComponent />;
   ```

---

## Success Metrics

Track these metrics to measure migration success:

- [ ] Lines of code reduced
- [ ] Number of components migrated
- [ ] Bugs introduced vs fixed
- [ ] Developer satisfaction
- [ ] Performance improvements
- [ ] Accessibility improvements

**Target Goals:**
- Reduce codebase by ~2,800 lines
- Migrate 158+ component instances
- Zero increase in bugs
- Improve load time by 10%
- Pass all accessibility audits

---

## Getting Help

1. **Documentation**
   - `QUICK_REFERENCE.md` - Quick lookup
   - `USAGE_EXAMPLES.md` - Detailed examples
   - `README.md` - Full documentation
   - Inline JSDoc comments

2. **Team Support**
   - Ask questions in team chat
   - Share migration experiences
   - Report bugs or issues
   - Suggest improvements

3. **Code Review**
   - Request review for migrated components
   - Share migration patterns that worked
   - Document lessons learned

---

## Timeline (Suggested)

### Week 1: Learning & Planning
- [ ] Read all documentation
- [ ] Identify components to migrate
- [ ] Create migration plan
- [ ] Set up testing environment

### Week 2-3: High Priority Migration
- [ ] Migrate forms with useFormState
- [ ] Migrate API calls with useApiRequest
- [ ] Test thoroughly

### Week 4-5: Medium Priority Migration
- [ ] Migrate loading states
- [ ] Migrate error displays
- [ ] Test accessibility

### Week 6: Low Priority & Polish
- [ ] Migrate remaining components
- [ ] Performance testing
- [ ] Documentation updates

---

## Completion Checklist

- [ ] All high-priority components migrated
- [ ] All tests passing
- [ ] Accessibility audit passed
- [ ] Performance benchmarks met
- [ ] Documentation updated
- [ ] Team trained on new components
- [ ] Old code removed
- [ ] Code review completed
- [ ] Deployed to production
- [ ] Monitoring for issues

---

**Last Updated:** April 2, 2026
**Version:** 1.0.0
