# Form Error Handling Guide

This guide explains how to add comprehensive error handling to all forms in the application.

## Features

- ✅ Display field-specific errors below each form field
- ✅ Highlight fields with errors using Bootstrap's `is-invalid` class
- ✅ Show non-field errors (general errors) at the top in UPPERCASE
- ✅ Extract errors from Django REST Framework responses automatically

## Quick Start

### 1. Import Required Utilities

```javascript
import {
  extractFormErrors,
  formatNonFieldErrors,
  getFieldError,
  getFieldErrorClass
} from '../utils/formErrors';
```

### 2. Add Error State to Component

```javascript
const [fieldErrors, setFieldErrors] = useState({});
const [nonFieldErrors, setNonFieldErrors] = useState([]);
```

### 3. Update Form Submit Handler

```javascript
const handleSubmit = async (e) => {
  e.preventDefault();
  setLoading(true);
  setFieldErrors({});  // Clear previous errors
  setNonFieldErrors([]);

  try {
    const response = await api.post('/your-endpoint/', formData);
    toast.success('Success!');
  } catch (error) {
    // Extract and set errors
    const { fieldErrors: errors, nonFieldErrors: nonErrors } = extractFormErrors(error);
    setFieldErrors(errors);
    setNonFieldErrors(nonErrors);

    // Show toast notification
    if (nonErrors.length > 0) {
      toast.error(formatNonFieldErrors(nonErrors));
    } else if (Object.keys(errors).length > 0) {
      toast.error('Please fix the errors in the form');
    } else {
      toast.error('Failed to save');
    }
  } finally {
    setLoading(false);
  }
};
```

### 4. Display Non-Field Errors (at top of form)

```javascript
{nonFieldErrors.length > 0 && (
  <div className="alert alert-danger mb-3" role="alert">
    <strong><i className="bi bi-exclamation-triangle-fill me-2"></i>ERROR:</strong>
    <div className="mt-1" style={{ textTransform: 'uppercase', fontWeight: '600' }}>
      {formatNonFieldErrors(nonFieldErrors)}
    </div>
  </div>
)}
```

### 5. Add Error Handling to Form Fields

#### For regular input fields:
```javascript
<div className="col-md-6">
  <label className="form-label fw-bold">Company Name *</label>
  <input
    type="text"
    className={`form-control ${getFieldErrorClass(fieldErrors, 'name')}`}
    value={formData.name}
    onChange={(e) => handleChange('name', e.target.value)}
    placeholder="Enter company name"
  />
  {getFieldError(fieldErrors, 'name') && (
    <div className="invalid-feedback">{getFieldError(fieldErrors, 'name')}</div>
  )}
</div>
```

#### For React-Select (AsyncSelect):
```javascript
<div className="col-md-6">
  <label className="form-label fw-bold">Company *</label>
  <AsyncSelect
    value={formData.company}
    loadOptions={loadCompanyOptions}
    onChange={(value) => handleChange('company', value)}
    className={getFieldError(fieldErrors, 'company') ? 'is-invalid' : ''}
  />
  {getFieldError(fieldErrors, 'company') && (
    <div className="invalid-feedback d-block">
      {getFieldError(fieldErrors, 'company')}
    </div>
  )}
</div>
```

#### For select fields:
```javascript
<div className="col-md-6">
  <label className="form-label fw-bold">Type</label>
  <select
    className={`form-select ${getFieldErrorClass(fieldErrors, 'type')}`}
    value={formData.type}
    onChange={(e) => handleChange('type', e.target.value)}
  >
    <option value="AT">Allotment</option>
    <option value="UT">Utilization</option>
  </select>
  {getFieldError(fieldErrors, 'type') && (
    <div className="invalid-feedback">{getFieldError(fieldErrors, 'type')}</div>
  )}
</div>
```

#### For textarea fields:
```javascript
<div className="col-md-12">
  <label className="form-label fw-bold">Description</label>
  <textarea
    className={`form-control ${getFieldErrorClass(fieldErrors, 'description')}`}
    value={formData.description}
    onChange={(e) => handleChange('description', e.target.value)}
    rows="3"
  />
  {getFieldError(fieldErrors, 'description') && (
    <div className="invalid-feedback">{getFieldError(fieldErrors, 'description')}</div>
  )}
</div>
```

## Using Reusable Components

For simpler forms, you can use the pre-built components:

```javascript
import { FormField, FormTextArea, FormSelect, NonFieldErrors } from '../components/FormField';
import { formatNonFieldErrors } from '../utils/formErrors';

// In your form:
<NonFieldErrors errors={nonFieldErrors} formatFunction={formatNonFieldErrors} />

<FormField
  label="Company Name"
  name="name"
  value={formData.name}
  onChange={handleChange}
  fieldErrors={fieldErrors}
  required
  placeholder="Enter company name"
/>

<FormTextArea
  label="Description"
  name="description"
  value={formData.description}
  onChange={handleChange}
  fieldErrors={fieldErrors}
  rows={4}
/>

<FormSelect
  label="Type"
  name="type"
  value={formData.type}
  onChange={handleChange}
  fieldErrors={fieldErrors}
  options={[
    { value: 'AT', label: 'Allotment' },
    { value: 'UT', label: 'Utilization' }
  ]}
/>
```

## Error Format from Django REST Framework

The utilities handle various DRF error response formats:

```javascript
// Field-specific errors
{
  "name": ["This field is required."],
  "email": ["Enter a valid email address."]
}

// Non-field errors
{
  "non_field_errors": ["Cannot create duplicate entry."]
}

// Generic error
{
  "detail": "Authentication credentials were not provided."
}
```

## Complete Example

See `frontend/src/components/AllotmentFormModal.jsx` for a complete implementation example.

## Utility Functions Reference

### `extractFormErrors(errorResponse)`
Extracts field errors and non-field errors from axios error response.

**Returns:** `{ fieldErrors: {}, nonFieldErrors: [] }`

### `formatNonFieldErrors(errors)`
Formats array of error messages to UPPERCASE string.

**Returns:** `string`

### `getFieldError(fieldErrors, fieldName)`
Gets error message for a specific field.

**Returns:** `string|null`

### `getFieldErrorClass(fieldErrors, fieldName)`
Gets CSS class for field based on error state.

**Returns:** `'is-invalid'` or `''`

### `hasFieldError(fieldErrors, fieldName)`
Checks if field has an error.

**Returns:** `boolean`

## Next Steps

Apply this pattern to all remaining forms:
- ✅ AllotmentFormModal.jsx (completed)
- ⏳ TradeForm.jsx
- ⏳ MasterFormModal.jsx
- ⏳ TransferLetterForm.jsx
- ⏳ Other form components

## Notes

- Always clear errors at the start of form submission
- Use `d-block` class with `invalid-feedback` for React-Select components
- Non-field errors are displayed in UPPERCASE for better visibility
- Field errors appear directly below the respective field
