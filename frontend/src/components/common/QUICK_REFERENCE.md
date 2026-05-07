# Common Components & Hooks - Quick Reference

## Import Statements

```javascript
// Hooks
import { useFormState, useApiRequest } from '@/hooks';

// Components (via index)
import {
  LoadingSpinner, PageSpinner, ButtonSpinner,
  ErrorAlert, ErrorMessage, SuccessMessage,
  FormField, FormSelect, FormTextArea,
  Modal, ConfirmModal, AlertModal
} from '@/components/common';

// Components (individual)
import { LoadingSpinner } from '@/components/common/LoadingSpinner';
import { ErrorAlert } from '@/components/common/ErrorAlert';
import { FormField } from '@/components/common/FormField';
import { Modal } from '@/components/common/Modal';
```

---

## useFormState - Quick Reference

### Basic Setup
```javascript
const {
  formData,        // Current form values
  errors,          // Validation errors
  touched,         // Touched fields
  isDirty,         // Form has changes
  isValid,         // Form is valid
  handleChange,    // Field change handler
  handleBlur,      // Field blur handler
  handleSubmit,    // Form submit handler
  resetForm        // Reset form
} = useFormState(initialValues, options);
```

### Common Options
```javascript
{
  validate: (values) => ({ field: 'error message' }),
  validateOnBlur: true,
  validateOnChange: false,
  warnBeforeUnload: true,
  enableReinitialize: false
}
```

### Common Patterns
```javascript
// Simple form
<input name="email" value={formData.email} onChange={handleChange} />

// With validation
<form onSubmit={handleSubmit(async (values) => {
  await api.post('/endpoint', values);
})}>

// Set field value
setFieldValue('email', 'test@example.com');

// Get field props
<input {...getFieldProps('email')} />
```

---

## useApiRequest - Quick Reference

### Basic Setup
```javascript
const {
  loading,      // Request in progress
  error,        // Error message
  data,         // Response data
  execute,      // Execute custom request
  get,          // GET request
  post,         // POST request
  put,          // PUT request
  patch,        // PATCH request
  delete: del,  // DELETE request
  cancel,       // Cancel request
  reset         // Reset state
} = useApiRequest(options);
```

### Common Options
```javascript
{
  showSuccessToast: true,
  showErrorToast: true,
  successMessage: 'Success!',
  retry: 3,
  retryDelay: 1000,
  cache: true,
  cacheTime: 5 * 60 * 1000,
  timeout: 10000
}
```

### Common Patterns
```javascript
// GET request
await get('/api/users', { page: 1 });

// POST request
await post('/api/users', userData);

// Custom request
await execute(() => api.post('/endpoint', data));

// With loading state
{loading && <LoadingSpinner />}
```

---

## LoadingSpinner - Quick Reference

### Variants
```jsx
// Default spinner
<LoadingSpinner />

// With text
<LoadingSpinner text="Loading..." />

// Different sizes
<LoadingSpinner size="sm|md|lg|xl" />

// Different variants
<LoadingSpinner variant="spinner|grow|dots|bars" />

// Different colors
<LoadingSpinner color="primary|success|danger|warning|info" />

// Overlay
<LoadingSpinner overlay text="Processing..." />

// Inline
<LoadingSpinner inline size="sm" />
```

### Pre-built Components
```jsx
<PageSpinner text="Loading page..." />
<ButtonSpinner /> // In buttons
<CardSpinner text="Loading content..." />
<InlineSpinner text="Processing..." />
```

---

## ErrorAlert - Quick Reference

### Variants
```jsx
// Basic error
<ErrorAlert severity="error" message="Error occurred" />

// With title
<ErrorAlert severity="warning" title="Warning" message="..." />

// With errors list
<ErrorAlert severity="error" errors={['Error 1', 'Error 2']} />

// Dismissible
<ErrorAlert dismissible onDismiss={() => {}} />

// Auto dismiss
<ErrorAlert autoDismiss autoDismissTimeout={3000} />

// With action
<ErrorAlert action={<button>Retry</button>} />
```

### Pre-built Components
```jsx
<ErrorMessage message="Error!" />
<WarningMessage message="Warning!" />
<InfoMessage message="Info!" />
<SuccessMessage message="Success!" />
<ValidationErrors errors={{ email: 'Invalid' }} />
<ApiError error={axiosError} />
```

### Severity Levels
- `error` / `danger` - Red alert
- `warning` - Yellow alert
- `info` - Blue alert
- `success` - Green alert

---

## FormField - Quick Reference

### Field Types
```jsx
// Text input
<FormField label="Name" name="name" value={v} onChange={h} />

// Email
<FormField label="Email" name="email" type="email" />

// Number
<FormField label="Age" name="age" type="number" />

// Select
<FormField
  label="Country"
  name="country"
  type="select"
  options={[
    { value: 'us', label: 'USA' },
    { value: 'uk', label: 'UK' }
  ]}
/>

// Textarea
<FormField label="Bio" name="bio" type="textarea" rows={4} />

// Checkbox
<FormField label="Agree" name="agree" type="checkbox" />

// Radio
<FormField
  label="Gender"
  name="gender"
  type="radio"
  options={['Male', 'Female', 'Other']}
/>
```

### Common Props
```jsx
<FormField
  label="Email"
  name="email"
  value={formData.email}
  onChange={handleChange}
  error={errors.email}
  required
  disabled
  helpText="Help text here"
  placeholder="Enter email"
  className="col-md-6"
/>
```

### Advanced Features
```jsx
// With prefix/suffix
<FormField prefix="bi-globe" suffix=".com" />

// Character count
<FormField maxLength={100} showCharCount />

// Floating label
<FormField floating />
```

### Pre-built Components
```jsx
<FormTextArea label="Bio" name="bio" />
<FormSelect label="Country" name="country" options={opts} />
<FormCheckbox label="Agree" name="agree" />
<FormRadio label="Gender" name="gender" options={opts} />
<FormGroup title="Personal Info">...</FormGroup>
```

---

## Modal - Quick Reference

### Basic Modal
```jsx
<Modal
  show={show}
  onHide={handleClose}
  title="Modal Title"
>
  Content
</Modal>
```

### With Footer
```jsx
<Modal
  show={show}
  onHide={handleClose}
  title="Modal Title"
  footer={
    <>
      <button onClick={handleClose}>Cancel</button>
      <button onClick={handleSave}>Save</button>
    </>
  }
>
  Content
</Modal>
```

### Sizes
```jsx
<Modal size="sm|md|lg|xl|fullscreen" />
```

### Options
```jsx
<Modal
  centered              // Center vertically
  scrollable            // Make body scrollable
  closeOnBackdrop={true}
  closeOnEscape={true}
  showCloseButton={true}
  loading={isLoading}
/>
```

### Pre-built Components
```jsx
// Confirmation
<ConfirmModal
  show={show}
  onHide={handleClose}
  onConfirm={handleConfirm}
  title="Confirm"
  message="Are you sure?"
  confirmText="Delete"
  confirmVariant="danger"
/>

// Alert
<AlertModal
  show={show}
  onHide={handleClose}
  title="Success"
  message="Done!"
  variant="success"
/>
```

---

## Common Patterns

### Complete Form
```jsx
function MyForm() {
  const { formData, errors, handleChange, handleSubmit } = useFormState(
    { name: '', email: '' },
    { validate: validateFn }
  );

  return (
    <form onSubmit={handleSubmit(async (values) => {
      await api.post('/endpoint', values);
    })}>
      <FormField
        label="Name"
        name="name"
        value={formData.name}
        onChange={handleChange}
        error={errors.name}
        required
      />
      <button type="submit">Submit</button>
    </form>
  );
}
```

### API Call with Loading
```jsx
function DataLoader() {
  const { get, loading, error, data } = useApiRequest();

  useEffect(() => {
    get('/api/data');
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorAlert severity="error" message={error} />;
  return <div>{JSON.stringify(data)}</div>;
}
```

### Modal Form
```jsx
function EditModal({ show, onHide }) {
  const { post, loading } = useApiRequest();
  const { formData, handleChange, handleSubmit } = useFormState(initialData);

  return (
    <Modal
      show={show}
      onHide={onHide}
      title="Edit"
      footer={
        <>
          <button onClick={onHide}>Cancel</button>
          <button onClick={handleSubmit(async (values) => {
            await post('/endpoint', values);
            onHide();
          })}>
            {loading && <ButtonSpinner />}
            Save
          </button>
        </>
      }
    >
      <FormField label="Name" name="name" {...formData} onChange={handleChange} />
    </Modal>
  );
}
```

---

## Prop Type Quick Reference

### useFormState Options
```javascript
{
  validate?: (values) => errors,
  validateOnChange?: boolean,
  validateOnBlur?: boolean,
  enableReinitialize?: boolean,
  warnBeforeUnload?: boolean,
  beforeUnloadMessage?: string
}
```

### useApiRequest Options
```javascript
{
  onSuccess?: (data) => void,
  onError?: (error) => void,
  showSuccessToast?: boolean,
  showErrorToast?: boolean,
  successMessage?: string,
  errorMessage?: string,
  retry?: number,
  retryDelay?: number,
  cache?: boolean,
  cacheTime?: number,
  timeout?: number
}
```

### LoadingSpinner Props
```javascript
{
  size?: 'sm'|'md'|'lg'|'xl',
  variant?: 'spinner'|'grow'|'dots'|'bars',
  color?: 'primary'|'success'|'danger'|'warning'|'info',
  text?: string,
  inline?: boolean,
  overlay?: boolean
}
```

### ErrorAlert Props
```javascript
{
  severity?: 'error'|'warning'|'info'|'success',
  title?: string,
  message?: string,
  errors?: string[],
  dismissible?: boolean,
  showIcon?: boolean,
  autoDismiss?: boolean
}
```

### FormField Props
```javascript
{
  label?: string,
  name: string,
  type?: 'text'|'email'|'select'|'textarea'|'checkbox'|'radio'|...,
  value?: any,
  onChange?: (e) => void,
  error?: string,
  required?: boolean,
  options?: array,
  helpText?: string,
  className?: string
}
```

### Modal Props
```javascript
{
  show: boolean,
  onHide: () => void,
  title?: string,
  footer?: ReactNode,
  size?: 'sm'|'md'|'lg'|'xl'|'fullscreen',
  centered?: boolean,
  scrollable?: boolean,
  closeOnBackdrop?: boolean,
  loading?: boolean
}
```

---

## Tips & Tricks

### Form Validation
```javascript
// Sync validation
validate: (values) => {
  const errors = {};
  if (!values.email) errors.email = 'Required';
  return errors;
}

// Async validation
validate: async (values) => {
  const errors = {};
  const exists = await api.get(`/check-email/${values.email}`);
  if (exists) errors.email = 'Email already exists';
  return errors;
}
```

### API Request Caching
```javascript
// Cache GET requests
const { get } = useApiRequest({ cache: true, cacheTime: 5 * 60 * 1000 });

// Clear cache
clearCache('user-1');
clearAllCache();
```

### Conditional Rendering
```javascript
// Loading
{loading && <LoadingSpinner />}

// Error
{error && <ErrorAlert severity="error" message={error} />}

// Data
{data && <DataDisplay data={data} />}
```

### Form Field Helpers
```javascript
// Get all field props
<input {...getFieldProps('email')} />

// Get field metadata
const { value, error, touched } = getFieldMeta('email');

// Field helpers
const { setValue, setTouched, setError } = getFieldHelpers('email');
```

---

For detailed documentation, see:
- `USAGE_EXAMPLES.md` - Comprehensive examples
- `README.md` - Full documentation
- Inline JSDoc comments - Code documentation
