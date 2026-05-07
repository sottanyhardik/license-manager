# Common Components and Hooks - Usage Examples

This document provides comprehensive usage examples for all the common components and hooks created to eliminate code duplication across the application.

## Table of Contents

1. [Hooks](#hooks)
   - [useFormState](#useformstate)
   - [useApiRequest](#useapirequest)
2. [Components](#components)
   - [LoadingSpinner](#loadingspinner)
   - [ErrorAlert](#erroralert)
   - [FormField](#formfield)
   - [Modal](#modal)

---

## Hooks

### useFormState

**Purpose**: Comprehensive form state management with validation, dirty tracking, and browser warnings.

#### Basic Usage

```jsx
import { useFormState } from '@/hooks';

function UserForm() {
  const {
    formData,
    errors,
    touched,
    isDirty,
    isValid,
    handleChange,
    handleBlur,
    handleSubmit,
    resetForm
  } = useFormState(
    { name: '', email: '', age: '' },
    {
      validate: (values) => {
        const errors = {};
        if (!values.name) errors.name = 'Name is required';
        if (!values.email) errors.email = 'Email is required';
        if (values.age && values.age < 18) errors.age = 'Must be 18 or older';
        return errors;
      },
      validateOnBlur: true,
      warnBeforeUnload: true
    }
  );

  const onSubmit = async (values) => {
    await api.post('/users', values);
    console.log('User created:', values);
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input
        name="name"
        value={formData.name}
        onChange={handleChange}
        onBlur={handleBlur}
      />
      {touched.name && errors.name && <span>{errors.name}</span>}

      <input
        name="email"
        type="email"
        value={formData.email}
        onChange={handleChange}
        onBlur={handleBlur}
      />
      {touched.email && errors.email && <span>{errors.email}</span>}

      <button type="submit" disabled={!isValid}>Submit</button>
      <button type="button" onClick={resetForm}>Reset</button>
    </form>
  );
}
```

#### Advanced Usage with Field Helpers

```jsx
function AdvancedForm() {
  const formState = useFormState(
    { email: '', password: '', confirmPassword: '' },
    {
      validate: (values) => {
        const errors = {};
        if (values.password !== values.confirmPassword) {
          errors.confirmPassword = 'Passwords must match';
        }
        return errors;
      },
      enableReinitialize: true
    }
  );

  const { getFieldProps, getFieldMeta, setFieldValue } = formState;

  return (
    <form>
      {/* Using getFieldProps */}
      <input {...getFieldProps('email')} type="email" />

      {/* Using getFieldMeta */}
      {getFieldMeta('email').error && getFieldMeta('email').touched && (
        <span>{getFieldMeta('email').error}</span>
      )}

      {/* Programmatic field updates */}
      <button onClick={() => setFieldValue('email', 'test@example.com')}>
        Fill Email
      </button>
    </form>
  );
}
```

---

### useApiRequest

**Purpose**: Enhanced API request hook with retry, caching, and cancellation support.

#### Basic Usage

```jsx
import { useApiRequest } from '@/hooks';

function UserList() {
  const { execute, loading, error, data } = useApiRequest({
    showSuccessToast: true,
    successMessage: 'Users loaded successfully',
    showErrorToast: true
  });

  useEffect(() => {
    execute(() => api.get('/users'));
  }, []);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorAlert severity="error" message={error} />;

  return (
    <ul>
      {data?.map(user => <li key={user.id}>{user.name}</li>)}
    </ul>
  );
}
```

#### Advanced Usage with Retry and Cache

```jsx
function DataFetcher() {
  const { get, post, loading, error, data, cancel } = useApiRequest({
    retry: 3,
    retryDelay: 1000,
    retryExponential: true,
    cache: true,
    cacheTime: 5 * 60 * 1000, // 5 minutes
    timeout: 10000, // 10 seconds
    showErrorToast: true
  });

  const loadData = async () => {
    const result = await get('/api/data', { page: 1, limit: 10 });
    if (result.success) {
      console.log('Data loaded:', result.data);
    }
  };

  const saveData = async (userData) => {
    const result = await post('/api/users', userData, {
      skipToast: false
    });

    if (result.success) {
      console.log('User saved:', result.data);
    }
  };

  return (
    <div>
      <button onClick={loadData} disabled={loading}>
        {loading ? 'Loading...' : 'Load Data'}
      </button>
      <button onClick={cancel} disabled={!loading}>
        Cancel
      </button>
    </div>
  );
}
```

#### Request Deduplication

```jsx
function DedupExample() {
  const { execute, loading } = useApiRequest({
    deduplicate: true
  });

  const fetchUser = (userId) => {
    return execute(
      () => api.get(`/users/${userId}`),
      { cacheKey: `user-${userId}` }
    );
  };

  // Multiple calls with same key will only execute once
  const loadData = async () => {
    await Promise.all([
      fetchUser(1),
      fetchUser(1), // This will use the result from the first call
      fetchUser(1)  // This too
    ]);
  };

  return <button onClick={loadData}>Load User</button>;
}
```

---

## Components

### LoadingSpinner

**Purpose**: Reusable loading spinner with multiple variants and sizes.

#### Basic Usage

```jsx
import { LoadingSpinner } from '@/components/common';

// Default spinner
<LoadingSpinner />

// Large spinner with text
<LoadingSpinner size="lg" text="Loading data..." />

// Different variants
<LoadingSpinner variant="dots" color="success" />
<LoadingSpinner variant="bars" color="primary" />
<LoadingSpinner variant="grow" color="warning" />
```

#### Inline Spinner in Button

```jsx
function SubmitButton({ loading, onClick }) {
  return (
    <button onClick={onClick} disabled={loading}>
      {loading && <LoadingSpinner size="sm" inline color="light" />}
      {loading ? ' Saving...' : 'Save'}
    </button>
  );
}
```

#### Full Page Overlay

```jsx
function SaveOperation() {
  const [saving, setSaving] = useState(false);

  return (
    <>
      {saving && <LoadingSpinner overlay text="Saving changes..." />}
      <button onClick={() => setSaving(true)}>Save</button>
    </>
  );
}
```

#### Pre-built Variants

```jsx
import {
  PageSpinner,
  ButtonSpinner,
  CardSpinner,
  InlineSpinner
} from '@/components/common';

// Page loading
<PageSpinner text="Loading page..." />

// In buttons
<button disabled>
  <ButtonSpinner /> Saving...
</button>

// In cards
<CardSpinner text="Loading content..." />

// Inline with text
<InlineSpinner text="Processing..." />
```

---

### ErrorAlert

**Purpose**: Reusable alert component for errors, warnings, success, and info messages.

#### Basic Usage

```jsx
import { ErrorAlert } from '@/components/common';

// Error message
<ErrorAlert severity="error" message="Something went wrong" />

// Warning with title
<ErrorAlert
  severity="warning"
  title="Warning"
  message="This action cannot be undone"
/>

// Success message
<ErrorAlert severity="success" message="Data saved successfully" />

// Info with dismissible
<ErrorAlert
  severity="info"
  message="New features available"
  dismissible
  onDismiss={() => console.log('dismissed')}
/>
```

#### Multiple Errors

```jsx
function ValidationDisplay({ errors }) {
  const errorList = [
    'Email is required',
    'Password must be at least 8 characters',
    'Passwords do not match'
  ];

  return (
    <ErrorAlert
      severity="error"
      title="Validation Errors"
      errors={errorList}
    />
  );
}
```

#### With Custom Action

```jsx
<ErrorAlert
  severity="warning"
  title="Session Expiring"
  message="Your session will expire in 5 minutes"
  action={
    <button className="btn btn-sm btn-warning">
      Extend Session
    </button>
  }
/>
```

#### Auto Dismiss

```jsx
<ErrorAlert
  severity="success"
  message="Changes saved successfully"
  autoDismiss
  autoDismissTimeout={3000}
/>
```

#### Pre-built Variants

```jsx
import {
  ErrorMessage,
  WarningMessage,
  InfoMessage,
  SuccessMessage,
  ValidationErrors,
  ApiError
} from '@/components/common';

// Simple messages
<ErrorMessage message="Error occurred" />
<WarningMessage message="Please be careful" />
<InfoMessage message="Did you know..." />
<SuccessMessage message="All done!" />

// Validation errors from form
<ValidationErrors errors={{ email: 'Invalid', password: 'Too short' }} />

// API error
<ApiError error={axiosError} />
```

---

### FormField

**Purpose**: Comprehensive form field wrapper with validation and accessibility.

#### Text Input

```jsx
import { FormField } from '@/components/common';

<FormField
  label="Email Address"
  name="email"
  type="email"
  value={formData.email}
  onChange={handleChange}
  error={errors.email}
  required
  placeholder="Enter your email"
  helpText="We'll never share your email"
/>
```

#### Select Field

```jsx
<FormField
  label="Country"
  name="country"
  type="select"
  value={formData.country}
  onChange={handleChange}
  options={[
    { value: 'us', label: 'United States' },
    { value: 'uk', label: 'United Kingdom' },
    { value: 'ca', label: 'Canada' }
  ]}
  placeholder="Select country..."
  error={errors.country}
/>
```

#### Textarea with Character Count

```jsx
<FormField
  label="Description"
  name="description"
  type="textarea"
  value={formData.description}
  onChange={handleChange}
  rows={4}
  maxLength={500}
  showCharCount
  error={errors.description}
/>
```

#### Checkbox

```jsx
<FormField
  label="I agree to terms and conditions"
  name="terms"
  type="checkbox"
  checked={formData.terms}
  onChange={handleChange}
  error={errors.terms}
  required
/>
```

#### Radio Buttons

```jsx
<FormField
  label="Gender"
  name="gender"
  type="radio"
  value={formData.gender}
  onChange={handleChange}
  options={[
    { value: 'male', label: 'Male' },
    { value: 'female', label: 'Female' },
    { value: 'other', label: 'Other' }
  ]}
/>
```

#### With Prefix/Suffix

```jsx
// With icon prefix
<FormField
  label="Website"
  name="website"
  type="url"
  value={formData.website}
  onChange={handleChange}
  prefix="bi-globe"
/>

// With text suffix
<FormField
  label="Price"
  name="price"
  type="number"
  value={formData.price}
  onChange={handleChange}
  prefix="$"
  suffix=".00"
/>
```

#### Floating Label

```jsx
<FormField
  label="Email Address"
  name="email"
  type="email"
  value={formData.email}
  onChange={handleChange}
  floating
/>
```

#### Form Group

```jsx
import { FormField, FormGroup } from '@/components/common';

<FormGroup title="Personal Information">
  <FormField
    label="First Name"
    name="firstName"
    value={formData.firstName}
    onChange={handleChange}
  />
  <FormField
    label="Last Name"
    name="lastName"
    value={formData.lastName}
    onChange={handleChange}
  />
</FormGroup>
```

---

### Modal

**Purpose**: Comprehensive modal dialog with customization and accessibility.

#### Basic Modal

```jsx
import { Modal } from '@/components/common';

function EditUser() {
  const [show, setShow] = useState(false);

  return (
    <>
      <button onClick={() => setShow(true)}>Edit User</button>

      <Modal
        show={show}
        onHide={() => setShow(false)}
        title="Edit User"
      >
        <form>
          <FormField label="Name" name="name" />
          <FormField label="Email" name="email" type="email" />
        </form>
      </Modal>
    </>
  );
}
```

#### Modal with Custom Footer

```jsx
<Modal
  show={show}
  onHide={handleClose}
  title="Confirm Delete"
  size="md"
  footer={
    <>
      <button className="btn btn-secondary" onClick={handleClose}>
        Cancel
      </button>
      <button className="btn btn-danger" onClick={handleDelete}>
        Delete
      </button>
    </>
  }
>
  Are you sure you want to delete this item?
</Modal>
```

#### Different Sizes

```jsx
// Small modal
<Modal show={show} onHide={handleClose} title="Small" size="sm">
  Content
</Modal>

// Medium modal
<Modal show={show} onHide={handleClose} title="Medium" size="md">
  Content
</Modal>

// Large modal
<Modal show={show} onHide={handleClose} title="Large" size="lg">
  Content
</Modal>

// Extra large modal (default)
<Modal show={show} onHide={handleClose} title="Extra Large" size="xl">
  Content
</Modal>

// Fullscreen modal
<Modal show={show} onHide={handleClose} title="Fullscreen" size="fullscreen">
  Content
</Modal>
```

#### Centered and Scrollable

```jsx
<Modal
  show={show}
  onHide={handleClose}
  title="Centered Modal"
  centered
  scrollable
>
  <div style={{ height: '1000px' }}>
    Long content...
  </div>
</Modal>
```

#### Loading State

```jsx
<Modal
  show={show}
  onHide={handleClose}
  title="Loading Data"
  loading={isLoading}
>
  Content will be hidden when loading
</Modal>
```

#### Prevent Close

```jsx
<Modal
  show={show}
  onHide={handleClose}
  title="Cannot Close"
  closeOnBackdrop={false}
  closeOnEscape={false}
  showCloseButton={false}
>
  You must complete this form
</Modal>
```

#### Pre-built Modal Variants

```jsx
import { ConfirmModal, AlertModal } from '@/components/common';

// Confirmation dialog
<ConfirmModal
  show={show}
  onHide={handleClose}
  onConfirm={handleConfirm}
  title="Confirm Delete"
  message="Are you sure you want to delete this item?"
  confirmText="Delete"
  confirmVariant="danger"
/>

// Alert dialog
<AlertModal
  show={show}
  onHide={handleClose}
  title="Success"
  message="Your changes have been saved"
  variant="success"
/>
```

---

## Complete Form Example

Here's a complete example using all components together:

```jsx
import React from 'react';
import {
  useFormState,
  useApiRequest
} from '@/hooks';
import {
  FormField,
  FormGroup,
  ErrorAlert,
  LoadingSpinner,
  Modal
} from '@/components/common';

function UserFormModal({ show, onHide, userId }) {
  const { execute, loading } = useApiRequest({
    showSuccessToast: true,
    successMessage: 'User saved successfully'
  });

  const {
    formData,
    errors,
    touched,
    isDirty,
    handleChange,
    handleBlur,
    handleSubmit,
    resetForm
  } = useFormState(
    {
      firstName: '',
      lastName: '',
      email: '',
      role: '',
      bio: ''
    },
    {
      validate: (values) => {
        const errors = {};
        if (!values.firstName) errors.firstName = 'First name is required';
        if (!values.lastName) errors.lastName = 'Last name is required';
        if (!values.email) errors.email = 'Email is required';
        if (!values.role) errors.role = 'Role is required';
        return errors;
      },
      validateOnBlur: true,
      warnBeforeUnload: true
    }
  );

  const onSubmit = async (values) => {
    const result = await execute(() =>
      userId
        ? api.put(`/users/${userId}`, values)
        : api.post('/users', values)
    );

    if (result.success) {
      resetForm();
      onHide();
    }
  };

  return (
    <Modal
      show={show}
      onHide={onHide}
      title={userId ? 'Edit User' : 'Create User'}
      size="lg"
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onHide}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-primary"
            onClick={handleSubmit(onSubmit)}
            disabled={loading || !isDirty}
          >
            {loading && <LoadingSpinner size="sm" inline color="light" />}
            {loading ? ' Saving...' : 'Save'}
          </button>
        </>
      }
    >
      <form onSubmit={handleSubmit(onSubmit)}>
        <FormGroup title="Personal Information">
          <FormField
            label="First Name"
            name="firstName"
            value={formData.firstName}
            onChange={handleChange}
            onBlur={handleBlur}
            error={errors.firstName}
            touched={touched.firstName}
            required
          />
          <FormField
            label="Last Name"
            name="lastName"
            value={formData.lastName}
            onChange={handleChange}
            onBlur={handleBlur}
            error={errors.lastName}
            touched={touched.lastName}
            required
          />
        </FormGroup>

        <FormGroup title="Account Details">
          <FormField
            label="Email"
            name="email"
            type="email"
            value={formData.email}
            onChange={handleChange}
            onBlur={handleBlur}
            error={errors.email}
            touched={touched.email}
            required
            className="col-md-12"
          />
          <FormField
            label="Role"
            name="role"
            type="select"
            value={formData.role}
            onChange={handleChange}
            error={errors.role}
            touched={touched.role}
            options={[
              { value: 'admin', label: 'Administrator' },
              { value: 'user', label: 'User' },
              { value: 'viewer', label: 'Viewer' }
            ]}
            placeholder="Select role..."
            required
            className="col-md-12"
          />
        </FormGroup>

        <FormGroup>
          <FormField
            label="Bio"
            name="bio"
            type="textarea"
            value={formData.bio}
            onChange={handleChange}
            rows={4}
            maxLength={500}
            showCharCount
            className="col-md-12"
            helpText="Tell us about yourself"
          />
        </FormGroup>
      </form>
    </Modal>
  );
}

export default UserFormModal;
```

---

## Best Practices

1. **Always use error boundaries** around components that use these hooks
2. **Memoize callbacks** when passing to these components/hooks
3. **Use TypeScript** for better type safety (optional but recommended)
4. **Keep validation logic separate** in utility files for reusability
5. **Use the common index** for imports: `import { FormField, Modal } from '@/components/common'`
6. **Leverage PropTypes** for runtime type checking in development
7. **Follow accessibility guidelines** - all components include ARIA attributes
8. **Test with different Bootstrap themes** to ensure styling consistency

---

## Migration Guide

### Migrating from Old Form Pattern

**Before:**
```jsx
const [formData, setFormData] = useState({});
const [errors, setErrors] = useState({});
const handleChange = (field, value) => {
  setFormData(prev => ({ ...prev, [field]: value }));
};
```

**After:**
```jsx
const { formData, errors, handleChange } = useFormState(initialData);
```

### Migrating from Old API Call Pattern

**Before:**
```jsx
const [loading, setLoading] = useState(false);
const [error, setError] = useState(null);
const fetchData = async () => {
  setLoading(true);
  try {
    const res = await api.get('/data');
    setData(res.data);
  } catch (err) {
    setError(err.message);
  } finally {
    setLoading(false);
  }
};
```

**After:**
```jsx
const { get, loading, error, data } = useApiRequest();
const fetchData = () => get('/data');
```

---

For more details, refer to the inline JSDoc comments in each component/hook file.
