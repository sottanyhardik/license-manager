# Form System V2

**Status:** Design Specification (Implementation pending)  
**Date:** 2026-09-25  
**Designer:** Product Design (25yr enterprise SPA specialist)

---

## Overview

The Form System defines the structure, spacing, validation patterns, and accessibility guidelines for all forms in the License Manager SPA. Forms are built from **Button**, **Input**, and **Label** primitives with a unified **FormField** wrapper that handles labeling, validation, and error display.

Key principle: **Consistent spacing, clear hierarchy, accessible-first design.**

---

## Spacing Scale

All form spacing follows the 4-point grid from Tabler tokens:

| Scale | Value | Use |
|-------|-------|-----|
| **Field Vertical** | 16px | Between label and input |
| **Field Spacing** | 16px | Between input and help text |
| **Group Spacing** | 24px | Between field groups (visually distinct sections) |
| **Section Spacing** | 32px | Between major form sections |
| **Form Padding** | 24px | Form container padding (all sides) |

---

## FormField Component Structure

The `FormField` wrapper encapsulates: label + input + help text/error + spacing.

```tsx
<FormField
  label="License Number"
  name="license_number"
  type="text"
  required={true}
  fieldErrors={errors}
  help="Enter the 10-digit license number"
/>
```

### Visual Structure

```
┌─────────────────────────────────────┐
│ License Number *                    │ ← Label (14px, 500wt, margin-bottom: 6px)
│ ┌──────────────────────────────────┐│ ← Input (40px height, 8px border-radius)
│ │ Enter license number here        ││
│ └──────────────────────────────────┘│
│ Enter the 10-digit license number   │ ← Help text (12px, gray, margin-top: 4px)
│                                     │
│ ↓ 16px margin-bottom               │
│                                     │
└─────────────────────────────────────┘
```

### HTML/Accessibility Structure

```html
<div className="FormField" style="margin-bottom: 16px;">
  <label htmlFor="license_number" className="mb-1.5 text-sm font-medium">
    License Number
    <span className="text-destructive ml-1" aria-label="required">*</span>
  </label>
  
  <input
    id="license_number"
    name="license_number"
    type="text"
    aria-required="true"
    aria-invalid="false"
    aria-describedby="license_number-help"
  />
  
  <p id="license_number-help" className="mt-1 text-xs text-muted-foreground">
    Enter the 10-digit license number
  </p>
</div>
```

---

## FormField API

```typescript
interface FormFieldProps {
  // Input definition
  label: string;
  name: string;
  type?: "text" | "email" | "password" | "number" | "tel" | "date" | "search";
  
  // Size variant
  size?: "compact-small" | "compact" | "default";  // Default: "default"
  
  // Validation
  required?: boolean;
  fieldErrors?: Record<string, any>;
  
  // Help & context
  help?: string;             // Help text below input
  placeholder?: string;
  
  // State
  disabled?: boolean;
  readonly?: boolean;
  
  // Extra
  className?: string;         // Wrapper class
  inputClassName?: string;    // Input class override
  id?: string;               // Custom ID (auto-generated if omitted)
  
  // HTML attributes pass-through
  [key: string]: any;
}
```

---

## Form Field Types

### Text Input
```tsx
<FormField 
  label="Full Name" 
  name="full_name" 
  type="text"
  required
/>
```

### Email Input
```tsx
<FormField 
  label="Email Address" 
  name="email" 
  type="email"
  required
  help="We'll never share your email."
/>
```

### Password Input
```tsx
<FormField 
  label="Password" 
  name="password" 
  type="password"
  required
  help="Minimum 8 characters"
/>
```

### Number Input
```tsx
<FormField 
  label="Quantity" 
  name="quantity" 
  type="number"
  min="1"
  step="1"
/>
```

### Date Input
```tsx
<FormField 
  label="License Issue Date" 
  name="issue_date" 
  type="date"
  required
/>
```

### Textarea (Multi-line)
```tsx
import { FormTextArea } from "@/components/FormField";

<FormTextArea 
  label="Notes" 
  name="notes"
  rows={4}
  help="Internal notes visible only to admins"
/>
```

### Select / Dropdown
```tsx
import { FormSelect } from "@/components/FormField";

<FormSelect 
  label="Status" 
  name="status"
  options={[
    { value: "draft", label: "Draft" },
    { value: "active", label: "Active" },
    { value: "archived", label: "Archived" },
  ]}
  required
/>
```

### Checkbox
```tsx
<div className="flex items-start gap-2 mb-4">
  <Checkbox id="agree" name="agree_terms" />
  <label htmlFor="agree" className="text-sm">
    I agree to the <a href="/terms" className="text-primary underline">Terms of Service</a>
  </label>
</div>
```

### Toggle / Switch
```tsx
<div className="flex items-center justify-between mb-4">
  <label htmlFor="notify" className="text-sm font-medium">
    Send Notifications
  </label>
  <Switch id="notify" name="notify" />
</div>
```

---

## Form Sections & Grouping

### Section Wrapper
Group related fields with visual separation:

```tsx
<div className="space-y-6">
  {/* Section 1 */}
  <fieldset className="border-t pt-6">
    <legend className="text-base font-semibold mb-4">License Details</legend>
    <div className="space-y-4">
      <FormField label="License Number" name="license_number" required />
      <FormField label="Issue Date" name="issue_date" type="date" required />
    </div>
  </fieldset>
  
  {/* Section 2 */}
  <fieldset className="border-t pt-6">
    <legend className="text-base font-semibold mb-4">Allotment Details</legend>
    <div className="space-y-4">
      <FormField label="Quantity" name="quantity" type="number" required />
      <FormField label="Value (CIF/FC)" name="value_cif" type="number" />
    </div>
  </fieldset>
</div>
```

### Spacing Utilities
```
space-y-4:   16px gap (between fields)
space-y-6:   24px gap (between groups)
space-y-8:   32px gap (between sections)
```

---

## Validation & Error States

### Field-Level Errors

When validation fails, display error in-place:

```tsx
<FormField 
  label="Quantity" 
  name="quantity" 
  type="number"
  fieldErrors={{ quantity: "Must be greater than 0" }}
/>
```

**Visual treatment:**
- Input border turns red (`aria-invalid:border-destructive`)
- Error text appears below input in red (12px, destructive color)
- Optional error icon (TriangleAlert, 12px) before text
- Message is `role="alert"` for screen readers

### Form-Level Errors

For non-field errors (API responses, validation rules):

```tsx
import { NonFieldErrors } from "@/components/FormField";

<form>
  <NonFieldErrors 
    errors={["License already exists", "Cannot update archived license"]}
    formatFunction={(errors) => `Please fix these issues: ${errors.join(", ")}`}
  />
  {/* Form fields */}
</form>
```

**Visual treatment:**
```
┌─────────────────────────────────────┐
│ ⚠ Error: Please fix these issues    │
│                                     │
│ - License already exists            │
│ - Cannot update archived license    │
└─────────────────────────────────────┘
```

- Background: `--tb-danger-soft` (#FEE2E2)
- Border: `--tb-danger/30` (#DC262630)
- Icon: TriangleAlert (16px, danger color)
- Text: 13px, danger color
- Padding: 12px
- Border-radius: 8px
- Margin-bottom: 16px

---

## Required Field Indicator

Required fields show a red asterisk after the label:

```tsx
<label>
  License Number
  <span className="text-destructive ml-1" aria-label="required">*</span>
</label>
```

**Visual:**
- Color: `--tb-danger` (red)
- Text: " *"
- Margin-left: 4px
- Accessible: `aria-label="required"` for screen readers

---

## Help Text

Clarifying text below the input:

```tsx
<FormField 
  label="Quantity" 
  name="quantity" 
  help="Maximum allowed: 1000 units based on your license plan"
/>
```

**Visual:**
- Font size: 12px (xs)
- Color: `--tb-text-tertiary` (#9CA3AF)
- Margin-top: 4px
- Font weight: Normal (400)
- Max width: 100% (no constraint)

---

## Form Actions Bar

Standard form submission buttons (Save, Cancel, Delete):

```tsx
<div className="flex gap-2 justify-end pt-6 border-t mt-6">
  <Button variant="ghost" onClick={onCancel}>
    Cancel
  </Button>
  {allowDelete && (
    <Button 
      variant="destructive" 
      onClick={onDelete}
      disabled={isDeleting}
    >
      {isDeleting ? <Loader2 className="animate-spin" /> : <Trash2 />}
      Delete
    </Button>
  )}
  <Button 
    onClick={onSave} 
    disabled={isLoading}
  >
    {isLoading ? <Loader2 className="animate-spin" /> : <Save />}
    Save
  </Button>
</div>
```

**Visual:**
- Layout: Flex row, justify-end (buttons flush right)
- Spacing: 8px between buttons
- Border-top: 1px (`--tb-border`)
- Padding-top: 16px
- Margin-top: 24px
- Responsive: Stack on mobile (flex-col reverse, justify-start)

**Button order (RTL):**
1. Save (primary, rightmost)
2. Delete (destructive, if allowed)
3. Cancel (ghost, leftmost)

---

## Form Layouts

### Single Column (Standard)
```tsx
<form className="space-y-4 max-w-md">
  <FormField label="Name" name="name" required />
  <FormField label="Email" name="email" type="email" required />
  <FormField label="Phone" name="phone" type="tel" />
  
  {/* Actions */}
  <div className="flex gap-2 justify-end pt-4 border-t mt-6">
    <Button variant="ghost">Cancel</Button>
    <Button>Save</Button>
  </div>
</form>
```

### Two Column (Side by side on desktop)
```tsx
<form className="space-y-6 max-w-2xl">
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
    <FormField label="First Name" name="first_name" required />
    <FormField label="Last Name" name="last_name" required />
  </div>
  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
    <FormField label="Email" name="email" type="email" required />
    <FormField label="Phone" name="phone" type="tel" />
  </div>
</form>
```

### Grouped Sections
```tsx
<form className="space-y-8 max-w-2xl">
  <fieldset>
    <legend className="text-lg font-semibold mb-4">Personal Information</legend>
    <div className="space-y-4">
      <FormField label="Full Name" name="name" required />
      <FormField label="Email" name="email" type="email" required />
    </div>
  </fieldset>
  
  <fieldset>
    <legend className="text-lg font-semibold mb-4">Preferences</legend>
    <div className="space-y-4">
      <FormField label="Timezone" name="timezone" required />
      <div className="flex items-center gap-2">
        <Checkbox id="notify" name="notify" />
        <Label htmlFor="notify">Send email notifications</Label>
      </div>
    </div>
  </fieldset>
</form>
```

---

## Form States

### Empty Form
All fields empty, form not yet submitted.

```
- All fields: Normal state (white background, gray border)
- Help text visible for each field
- Save button: Enabled (unless required fields empty)
- Errors: None visible
```

### Filled Form
User has entered data; form ready for submission.

```
- Fields: May show value (no visual change)
- Validation: On blur (real-time) or on submit (batch)
- Errors: Appear only if validation fails
- Save button: Enabled
```

### Submitted (Loading)
Form submission in progress.

```
- All inputs: Disabled
- Save button: Disabled + loading spinner + "Saving..." text
- Form-level errors: Not shown (show after submission completes)
- User action: Cannot submit again (disabled)
```

### Submission Error
Form submission failed; server returned error.

```
- Form-level errors: Show NonFieldErrors banner at top
- Field errors: Show inline for affected fields only
- Inputs: Re-enabled for correction
- Save button: Re-enabled (enabled to retry)
```

### Submission Success
Form successfully submitted.

```
- Toast notification: "Changes saved successfully" (success tone)
- Form may close (modal context) or reset (standalone form)
- Errors: Cleared
```

---

## Modal Forms

Forms inside a `<Dialog>` or `<Modal>`:

```tsx
<Dialog>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Create New Allotment</DialogTitle>
    </DialogHeader>
    
    <form className="space-y-4">
      <FormField label="License" name="license" required />
      <FormField label="Quantity" name="quantity" type="number" required />
      <FormField label="Notes" name="notes" />
    </form>
    
    <DialogFooter className="flex gap-2 justify-end pt-4 border-t">
      <Button variant="ghost" onClick={onClose}>
        Cancel
      </Button>
      <Button onClick={onSubmit}>
        Create
      </Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

**Differences from page forms:**
- Content area has max width (e.g., `max-w-md`)
- Actions in `<DialogFooter>` (styled as flex row, right-aligned)
- No top-level margin (modal handles spacing)
- Typically single-column layout

---

## Accessibility (WCAG AA)

### Labels
- Every input has `<label htmlFor={id}>`
- Custom labels (checkbox/radio): Click-to-select (label wraps or uses `htmlFor`)
- Required: Marked with `*` + `aria-label="required"`

### Validation
- Invalid fields: `aria-invalid="true"`
- Error message: `aria-describedby="error-id"`
- Error text: `role="alert"` (announced to screen readers)
- Help text: `aria-describedby="help-id"` (optional)

### Keyboard Navigation
- Tab: Move between fields left-to-right, top-to-bottom
- Shift+Tab: Move backward
- Enter: Submit form (if there's a submit button)
- Space: Toggle checkbox/radio/switch
- Arrow keys: Navigate select menu options

### Focus Management
- Visual focus: 3px ring visible on all inputs
- Focus outline: No outline (ring handles it)
- Initial focus: First input in form (auto-focus if appropriate)

### Color & Contrast
- Error text: 4.5:1 contrast minimum (red on white background)
- Placeholder: 3:1 minimum (lighter gray is OK)
- Labels: 4.5:1 minimum (black on white, white on dark)

---

## Common Patterns

### Login Form
```tsx
<form className="space-y-4 max-w-sm">
  <FormField 
    label="Email" 
    name="email" 
    type="email"
    required 
  />
  <FormField 
    label="Password" 
    name="password" 
    type="password"
    required 
  />
  <Button className="w-full">
    Sign In
  </Button>
</form>
```

### Search Form
```tsx
<form className="flex gap-2">
  <Input 
    type="search" 
    placeholder="Search licenses..."
    className="flex-1"
  />
  <Button variant="outline">
    <Search className="size-4" />
    Search
  </Button>
</form>
```

### Inline Editing
```tsx
const [isEditing, setIsEditing] = useState(false);

return isEditing ? (
  <form className="inline-flex gap-2">
    <Input type="text" defaultValue={value} />
    <Button size="compact" onClick={() => setIsEditing(false)}>Save</Button>
  </form>
) : (
  <div className="flex gap-2 items-center">
    <span>{value}</span>
    <Button 
      variant="ghost" 
      size="icon"
      onClick={() => setIsEditing(true)}
    >
      <Edit className="size-4" />
    </Button>
  </div>
);
```

---

## Form Component Files

**Current:**
- `frontend/src/components/FormField.tsx` — FormField, FormTextArea, FormSelect, NonFieldErrors
- `frontend/src/components/ui/input.tsx` — Input primitive
- `frontend/src/components/ui/label.tsx` — Label primitive

**To create/update:**
1. Extend FormField.tsx with size variants
2. Create FormDateRange component (two date inputs)
3. Create FormCheckbox component (checkbox + label)
4. Create FormSwitch component (switch + label)
5. Update FormSelect to use new Select component

---

## Migration Path

| Current | V2 | Notes |
|---------|----|----|
| FormField (label, input, error) | FormField (enhanced with sizes) | API same, add size prop |
| FormTextArea | FormTextArea | No change |
| FormSelect | FormSelect | Update to use new Select component |
| `mb-2` label spacing | `mb-1.5` + input style | Tighten from 8px to 6px |
| `mt-1` error spacing | `mt-1` | Keep (4px gap looks right) |
| Space between fields | Use `space-y-4` utility | Explicit 16px gap |
| Space between groups | Manual margin | Use `space-y-6` utility (24px) |

---

## Token References

- `--tb-text`: Label color (#111827)
- `--tb-text-tertiary`: Help text color (#9CA3AF)
- `--tb-danger`: Error/required color (#DC2626)
- `--tb-danger-soft`: Error background (#FEE2E2)
- `--tb-border`: Separator color (#E4E7EC)
- `--tb-sp-4`: 16px (field vertical spacing)
- `--tb-sp-6`: 24px (group spacing)
- `--tb-sp-8`: 32px (section spacing)

---

**END OF SPECIFICATION**
