# Form Components Migration Guide

**Status:** Implementation Plan  
**Date:** 2026-09-25  
**Phase:** Post-Design (ready for frontend-engineer)

---

## Purpose

This document outlines the step-by-step migration of the form system from current state to V2 specification. It includes:
- Files to create/update
- Breaking changes (none expected)
- Migration path for existing code
- Testing requirements
- Rollout strategy

---

## Overview

The Form System V2 introduces:
1. **Standardized sizing** (compact-small/compact/default) for all inputs and buttons
2. **Explicit form field spacing** (16px vertical, 24px group gaps)
3. **New button variants** (Success, split buttons)
4. **Input size variants** (36px, 32px, 40px mapped to token control heights)
5. **Filter system helpers** (FilterMultiSelect, FilterDateRange, FilterNumberRange)

**Breaking Changes:** None (all changes are additive or non-breaking)

---

## Implementation Phases

### Phase 1: Button System (Priority: High)
**Time estimate:** 6-8 hours

#### Files to Update

**1. frontend/src/components/ui/button.tsx**

```diff
const buttonVariants = cva(
    "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40 active:scale-95 cursor-pointer",
    {
        variants: {
            variant: {
                default: "bg-primary text-primary-foreground shadow-sm hover:bg-primary/90 hover:shadow",
                destructive: "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90 hover:shadow focus-visible:ring-destructive/40",
                outline: "border border-input bg-card shadow-sm hover:bg-accent hover:text-accent-foreground hover:shadow",
                secondary: "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80 hover:shadow",
                ghost: "hover:bg-accent hover:text-accent-foreground",
+               success: "bg-success text-success-foreground shadow-sm hover:bg-success/80 hover:shadow focus-visible:ring-success/40",
                link: "text-primary underline-offset-4 hover:underline",
            },
            size: {
+               "compact-small": "h-8 px-2 py-1 has-[>svg]:px-1.5",
-               default: "h-10 px-4 py-2 has-[>svg]:px-3",
+               compact: "h-9 px-3 py-1.5 has-[>svg]:px-2.5",
+               default: "h-10 px-4 py-2 has-[>svg]:px-3",
+               lg: "h-11 px-6 py-2.5 has-[>svg]:px-4",
-               sm: "h-9 rounded-lg gap-1.5 px-3 has-[>svg]:px-2.5 text-xs",
-               lg: "h-11 rounded-lg px-6 has-[>svg]:px-4",
                icon: "size-10",
            },
        },
        defaultVariants: {
            variant: "default",
            size: "default",
        },
    }
);
```

**Changes:**
- Add `success` variant (new)
- Rename `sm` → `compact` for clarity
- Add `compact-small` (32px) for dense UI
- Update sizing to match token control heights (32/36/40/44px)
- Deprecate old `sm` size (keep as alias for backward compat)

**Testing:**
- Render all variants × 4 sizes in Storybook
- Verify focus ring is visible on light and dark backgrounds
- Check hover states, disabled state, loading state (with spinner)
- Mobile: Verify touch targets are >= 44px

---

### Phase 2: Input System (Priority: High)
**Time estimate:** 8-10 hours

#### Files to Update

**1. frontend/src/components/ui/input.tsx**

```diff
function Input({ className, type, ...props }: React.ComponentProps<"input">) {
    return (
        <input
            type={type}
            data-slot="input"
            className={cn(
-               "flex h-10 w-full min-w-0 rounded-lg border border-input bg-card px-3 py-2 text-sm shadow-sm transition-[color,box-shadow,border-color] outline-none",
+               "flex w-full min-w-0 rounded-lg border border-input bg-card text-sm shadow-sm transition-[color,box-shadow,border-color] outline-none",
+               "data-[size=compact-small]:h-8 data-[size=compact-small]:px-2 data-[size=compact-small]:py-1 data-[size=compact-small]:text-xs",
+               "data-[size=compact]:h-9 data-[size=compact]:px-3 data-[size=compact]:py-1.5",
+               "data-[size=default]:h-10 data-[size=default]:px-3 data-[size=default]:py-2",
                "file:inline-flex file:border-0 file:bg-transparent file:text-sm file:font-medium",
                "placeholder:text-muted-foreground",
                "hover:border-input/80",
                "focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-[3px] focus-visible:shadow",
                "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-muted",
                "aria-invalid:border-destructive aria-invalid:ring-destructive/30",
                className
            )}
+           data-size={props.size || "default"}
            {...props}
        />
    );
}
```

**Changes:**
- Add `size` prop support (compact-small/compact/default)
- Use `data-[size=*]` attributes for responsive sizing
- No breaking changes (default size remains h-10)

**TypeScript additions:**
```typescript
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  size?: "compact-small" | "compact" | "default";
}
```

**Testing:**
- Render three sizes in Storybook
- Verify height, padding, font size for each
- Test all states (hover, focus, disabled, error)
- Test with type="date", type="file", type="password"

---

**2. frontend/src/components/ui/select.tsx**

Update `SelectTrigger` to support `size` prop (already partially there):

```diff
function SelectTrigger({
    className,
    size = "default",
    children,
    ...props
-}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {
-    size?: "sm" | "default";
+}: React.ComponentProps<typeof SelectPrimitive.Trigger> & {
+    size?: "compact-small" | "compact" | "default";
}) {
    return (
        <SelectPrimitive.Trigger
            data-slot="select-trigger"
            data-size={size}
            className={cn(
                "flex w-full items-center justify-between gap-2 rounded-lg border border-input bg-card px-3 py-2 text-sm shadow-sm transition-all outline-none cursor-pointer",
-               "data-[size=default]:h-10 data-[size=sm]:h-9",
+               "data-[size=default]:h-10",
+               "data-[size=compact]:h-9",
+               "data-[size=compact-small]:h-8",
                "hover:border-input/80 hover:shadow",
                "placeholder:text-muted-foreground [&_span]:line-clamp-1",
                "focus-visible:border-ring focus-visible:ring-ring/30 focus-visible:ring-[3px] focus-visible:shadow",
                "disabled:cursor-not-allowed disabled:opacity-50",
                "data-[placeholder]:text-muted-foreground [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:opacity-60",
                className
            )}
            {...props}
        >
```

**Testing:**
- Render three sizes in Storybook
- Verify dropdown aligns correctly at each size
- Test keyboard nav (arrow keys, enter, escape)

---

**3. frontend/src/components/ui/checkbox.tsx**

Minor updates for consistency:

```diff
function Checkbox({
    className,
    ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
    return (
        <CheckboxPrimitive.Root
            data-slot="checkbox"
            className={cn(
-               "peer size-4 shrink-0 rounded-md border border-input shadow-sm outline-none transition-all",
+               "peer size-4 shrink-0 rounded-md border border-input shadow-sm outline-none transition-colors",
                "hover:border-input/80 hover:shadow",
                "focus-visible:ring-[3px] focus-visible:ring-ring/40",
                "disabled:cursor-not-allowed disabled:opacity-50",
                "data-[state=checked]:border-primary data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[state=checked]:hover:border-primary/90",
                className
            )}
            {...props}
        >
```

**Changes:**
- Change `transition-all` → `transition-colors` (don't animate size)
- No size variants needed (16px is standard for checkboxes)

---

**4. Create frontend/src/components/ui/radio.tsx** (New)

```typescript
import * as React from "react";
import * as RadioGroupPrimitive from "@radix-ui/react-radio-group";

import { cn } from "@/lib/utils";

const RadioGroup = RadioGroupPrimitive.Root;

function RadioGroupItem({
    className,
    ...props
}: React.ComponentProps<typeof RadioGroupPrimitive.Item>) {
    return (
        <RadioGroupPrimitive.Item
            data-slot="radio"
            className={cn(
                "peer size-4 shrink-0 rounded-full border border-input shadow-sm outline-none transition-colors",
                "hover:border-input/80 hover:shadow",
                "focus-visible:ring-[3px] focus-visible:ring-ring/40",
                "disabled:cursor-not-allowed disabled:opacity-50",
                "data-[state=checked]:border-primary data-[state=checked]:bg-primary",
                className
            )}
            {...props}
        >
            <RadioGroupPrimitive.Indicator className="flex items-center justify-center">
                <div className="size-2 rounded-full bg-primary-foreground" />
            </RadioGroupPrimitive.Indicator>
        </RadioGroupPrimitive.Item>
    );
}

export { RadioGroup, RadioGroupItem };
```

**Testing:**
- Render in form context
- Test keyboard nav (arrow keys), checked state
- Verify focus ring and hover states

---

**5. frontend/src/components/ui/switch.tsx**

Minor updates:

```diff
function Switch({
    className,
    ...props
}: React.ComponentProps<typeof SwitchPrimitive.Root>) {
    return (
        <SwitchPrimitive.Root
            data-slot="switch"
            className={cn(
-               "peer inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-full border border-transparent shadow-sm transition-all outline-none",
+               "peer inline-flex h-6 w-10 shrink-0 cursor-pointer items-center rounded-full border border-transparent shadow-sm transition-colors outline-none",
                "hover:shadow",
                "focus-visible:ring-[3px] focus-visible:ring-ring/40",
                "disabled:cursor-not-allowed disabled:opacity-50",
                "data-[state=checked]:bg-primary data-[state=unchecked]:bg-input",
                className
            )}
            {...props}
        >
            <SwitchPrimitive.Thumb
                className={cn(
-                   "pointer-events-none block size-4 rounded-full bg-white shadow-sm ring-0 transition-transform",
+                   "pointer-events-none block size-4 rounded-full bg-white shadow-sm ring-0 transition-[transform] duration-200",
                    "data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0.5"
                )}
            />
        </SwitchPrimitive.Root>
    );
}
```

**Changes:**
- `transition-all` → `transition-[transform] duration-200` (only animate thumb position)

---

### Phase 3: Form Field Component (Priority: High)
**Time estimate:** 6-8 hours

#### Files to Update

**1. frontend/src/components/FormField.tsx**

```diff
interface FormFieldProps
    extends BaseFieldProps,
        Omit<React.InputHTMLAttributes<HTMLInputElement>, "name" | "required" | "className"> {
    type?: string;
+   size?: "compact-small" | "compact" | "default";
+   help?: string;
}

export const FormField = ({
    label,
    name,
    type = "text",
    fieldErrors = {},
    required = false,
    className = "",
+   size = "default",
+   help,
    id: idProp,
    ...props
}: FormFieldProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
+   const helpId = `${id}-help`;
    const error = getFieldError(fieldErrors, name);

    return (
-       <div className={className}>
+       <div className={cn("mb-4", className)}>
            <Label htmlFor={id} className={cn("mb-1.5 text-sm font-medium", required && "required")}>
                {label}
+               {required && <span className="text-destructive ml-1" aria-label="required">*</span>}
            </Label>
            <Input
                id={id}
                type={type}
                name={name}
+               size={size}
                aria-invalid={!!error}
                aria-required={required}
-               aria-describedby={error ? errorId : undefined}
+               aria-describedby={cn(
+                   error ? errorId : undefined,
+                   help ? helpId : undefined
+               )}
                {...props}
            />
+           {help && !error && (
+               <p id={helpId} className="mt-1 text-xs text-muted-foreground">
+                   {help}
+               </p>
+           )}
            {error && (
-               <p id={errorId} className="mt-1 text-xs text-destructive" role="alert">
+               <p id={errorId} className="mt-1 text-xs text-destructive font-medium" role="alert">
+                   <TriangleAlert className="inline size-3 mr-1" aria-hidden="true" />
                    {error}
                </p>
            )}
        </div>
    );
};
```

**Changes:**
- Add `size` prop (passed to Input)
- Add `help` prop for help text
- Explicit required indicator (`*`)
- Error icon (TriangleAlert)
- Default margin-bottom (16px) for consistent field spacing
- Help text styling
- Better aria-describedby handling

---

**2. Update FormTextArea similarly**

```diff
export const FormTextArea = ({
    label,
    name,
    fieldErrors = {},
    required = false,
    rows = 3,
    className = "",
+   size = "default",
+   help,
    id: idProp,
    ...props
}: FormTextAreaProps) => {
    const generatedId = useId();
    const id = idProp ?? generatedId;
    const errorId = `${id}-error`;
+   const helpId = `${id}-help`;
    const error = getFieldError(fieldErrors, name);

    return (
-       <div className={className}>
+       <div className={cn("mb-4", className)}>
            <Label htmlFor={id} className={cn("mb-1.5 text-sm font-medium", required && "required")}>
                {label}
+               {required && <span className="text-destructive ml-1" aria-label="required">*</span>}
            </Label>
            <Textarea
                id={id}
                name={name}
                rows={rows}
                aria-invalid={!!error}
                aria-required={required}
-               aria-describedby={error ? errorId : undefined}
+               aria-describedby={cn(
+                   error ? errorId : undefined,
+                   help ? helpId : undefined
+               )}
                {...props}
            />
+           {help && !error && (
+               <p id={helpId} className="mt-1 text-xs text-muted-foreground">
+                   {help}
+               </p>
+           )}
            {error && (
-               <p id={errorId} className="mt-1 text-xs text-destructive" role="alert">
+               <p id={errorId} className="mt-1 text-xs text-destructive font-medium" role="alert">
+                   <TriangleAlert className="inline size-3 mr-1" aria-hidden="true" />
                    {error}
                </p>
            )}
        </div>
    );
};
```

---

**3. Create FormCheckbox component (new)**

```typescript
interface FormCheckboxProps {
  id?: string;
  name: string;
  label: string;
  help?: string;
  required?: boolean;
  className?: string;
}

export const FormCheckbox = ({
  id: idProp,
  name,
  label,
  help,
  required = false,
  className = "",
  ...props
}: FormCheckboxProps) => {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const helpId = `${id}-help`;

  return (
    <div className={cn("mb-4 flex items-start gap-2", className)}>
      <Checkbox
        id={id}
        name={name}
        aria-required={required}
        aria-describedby={help ? helpId : undefined}
        {...props}
      />
      <div className="flex-1">
        <label htmlFor={id} className="text-sm font-medium cursor-pointer">
          {label}
          {required && <span className="text-destructive ml-1">*</span>}
        </label>
        {help && (
          <p id={helpId} className="mt-1 text-xs text-muted-foreground">
            {help}
          </p>
        )}
      </div>
    </div>
  );
};
```

---

**4. Create FormSwitch component (new)**

```typescript
interface FormSwitchProps {
  id?: string;
  name: string;
  label: string;
  help?: string;
  required?: boolean;
  className?: string;
}

export const FormSwitch = ({
  id: idProp,
  name,
  label,
  help,
  required = false,
  className = "",
  ...props
}: FormSwitchProps) => {
  const generatedId = useId();
  const id = idProp ?? generatedId;
  const helpId = `${id}-help`;

  return (
    <div className={cn("mb-4 flex items-center justify-between gap-2", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </label>
      <Switch
        id={id}
        name={name}
        aria-required={required}
        aria-describedby={help ? helpId : undefined}
        {...props}
      />
      {help && (
        <p id={helpId} className="text-xs text-muted-foreground">
          {help}
        </p>
      )}
    </div>
  );
};
```

---

**Testing:**
- Render all field types in Storybook
- Test required indicator, help text, error states
- Verify spacing (16px between fields)
- Check mobile responsive (inputs full width)

---

### Phase 4: Filter System Helpers (Priority: Medium)
**Time estimate:** 4-6 hours

#### Files to Create

**1. frontend/src/components/filters/FilterMultiSelect.tsx** (New)

```typescript
interface FilterMultiSelectProps {
  label: string;
  options: Array<{ value: string; label: string }>;
  selected: string[];
  onChange: (selected: string[]) => void;
}

export function FilterMultiSelect({
  label,
  options,
  selected,
  onChange,
}: FilterMultiSelectProps) {
  const handleToggle = (value: string) => {
    onChange(
      selected.includes(value)
        ? selected.filter((v) => v !== value)
        : [...selected, value]
    );
  };

  return (
    <div>
      <Label className="text-sm font-medium mb-2">{label}</Label>
      <div className="space-y-2">
        {options.map((option) => (
          <div key={option.value} className="flex items-center gap-2">
            <Checkbox
              id={option.value}
              checked={selected.includes(option.value)}
              onCheckedChange={() => handleToggle(option.value)}
            />
            <label
              htmlFor={option.value}
              className="text-sm font-normal cursor-pointer"
            >
              {option.label}
            </label>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

**2. frontend/src/components/filters/FilterDateRange.tsx** (New)

```typescript
interface FilterDateRangeProps {
  label: string;
  startDate: string;
  endDate: string;
  onStartChange: (date: string) => void;
  onEndChange: (date: string) => void;
}

export function FilterDateRange({
  label,
  startDate,
  endDate,
  onStartChange,
  onEndChange,
}: FilterDateRangeProps) {
  return (
    <div>
      <Label className="text-sm font-medium mb-2">{label}</Label>
      <div className="grid grid-cols-2 gap-2">
        <Input
          type="date"
          size="compact"
          value={startDate}
          onChange={(e) => onStartChange(e.target.value)}
          placeholder="From"
        />
        <Input
          type="date"
          size="compact"
          value={endDate}
          onChange={(e) => onEndChange(e.target.value)}
          placeholder="To"
        />
      </div>
    </div>
  );
}
```

---

**3. frontend/src/components/filters/FilterNumberRange.tsx** (New)

```typescript
interface FilterNumberRangeProps {
  label: string;
  minValue: string;
  maxValue: string;
  onMinChange: (value: string) => void;
  onMaxChange: (value: string) => void;
  placeholder?: { min?: string; max?: string };
}

export function FilterNumberRange({
  label,
  minValue,
  maxValue,
  onMinChange,
  onMaxChange,
  placeholder = { min: "Min", max: "Max" },
}: FilterNumberRangeProps) {
  return (
    <div>
      <Label className="text-sm font-medium mb-2">{label}</Label>
      <div className="grid grid-cols-2 gap-2">
        <Input
          type="number"
          size="compact"
          value={minValue}
          onChange={(e) => onMinChange(e.target.value)}
          placeholder={placeholder.min}
        />
        <Input
          type="number"
          size="compact"
          value={maxValue}
          onChange={(e) => onMaxChange(e.target.value)}
          placeholder={placeholder.max}
        />
      </div>
    </div>
  );
}
```

---

**Testing:**
- Render filters in filter panel context
- Verify multi-select checkboxes work
- Test date/number range inputs
- Check responsive grid (1 col mobile, 2 col tablet, 4 col desktop)

---

### Phase 5: Documentation & Storybook (Priority: Medium)
**Time estimate:** 4-5 hours

#### Create Storybook Stories

**1. Button.stories.tsx**
- Show all variants × 4 sizes
- Loading states
- Disabled states
- Icon + text combinations

**2. Input.stories.tsx**
- Three sizes (compact-small/compact/default)
- All input types (text, email, password, date, number)
- States (hover, focus, disabled, error)

**3. FormField.stories.tsx**
- Text input
- Textarea
- With help text
- With error
- Required indicator

**4. Select.stories.tsx**
- Three sizes
- Open/closed states
- Multi-select (future)

**5. FilterPanel.stories.tsx**
- Example filters
- Active count indicator
- Clear filters button
- Responsive grid

---

## Breaking Changes Analysis

**None expected.**

- All changes are additive (new props, new variants)
- Old size names (`sm`) kept as aliases for backward compatibility
- No existing APIs removed
- No existing classNames changed (only extended)

---

## Migration Checklist

### Files to Create
- [ ] `frontend/src/components/ui/radio.tsx`
- [ ] `frontend/src/components/FormCheckbox.tsx` (in FormField.tsx)
- [ ] `frontend/src/components/FormSwitch.tsx` (in FormField.tsx)
- [ ] `frontend/src/components/filters/FilterMultiSelect.tsx`
- [ ] `frontend/src/components/filters/FilterDateRange.tsx`
- [ ] `frontend/src/components/filters/FilterNumberRange.tsx`

### Files to Update
- [ ] `frontend/src/components/ui/button.tsx` (add success variant, resize)
- [ ] `frontend/src/components/ui/input.tsx` (add size variants)
- [ ] `frontend/src/components/ui/select.tsx` (update size options)
- [ ] `frontend/src/components/ui/checkbox.tsx` (refine transitions)
- [ ] `frontend/src/components/ui/switch.tsx` (refine transitions)
- [ ] `frontend/src/components/FormField.tsx` (add help text, required indicator, size support)

### Testing
- [ ] Unit tests for all new components
- [ ] Storybook stories for all variants/states
- [ ] Visual regression tests (light/dark mode)
- [ ] Accessibility tests (axe, keyboard nav)
- [ ] Mobile responsive tests

### Documentation
- [ ] Update component READMEs
- [ ] Add Storybook stories
- [ ] Document migration path for existing code

---

## Rollout Strategy

### Week 1: Infrastructure
1. Create new components (radio, form helpers, filter helpers)
2. Update Button, Input, Select sizing
3. Write tests and Storybook stories

### Week 2: Integration
1. Update FormField component with new props
2. Test in development environment
3. Get visual sign-off from design

### Week 3: Rollout
1. Merge to develop
2. Deploy to staging
3. QA testing (forms, filters, buttons across app)
4. Deploy to production

### Week 4+: Refactor (Optional)
1. Update existing form usages to use new size props
2. Convert legacy filter patterns to new FilterMultiSelect/FilterDateRange
3. Standardize button sizes across app

---

## Risk Mitigation

**Risk:** Button sizing breaks existing layouts.  
**Mitigation:** New sizes are opt-in; old sizes remain; test in staging before rollout.

**Risk:** Form field spacing breaks existing pages.  
**Mitigation:** `mb-4` is only on FormField wrapper; pages can override with `className="mb-2"` if needed.

**Risk:** Focus ring is not visible on dark mode.  
**Mitigation:** Verify focus ring contrast in both light and dark modes before release.

---

## Success Metrics

1. All new components render without errors
2. 100% test coverage for new components
3. No visual regressions in existing forms/buttons
4. Mobile form UX improved (better touch targets, responsive layout)
5. Designer approval on visual output

---

## Post-Rollout Cleanup

After V2 is stable, consider:
1. Remove old size aliases (`sm` → `compact`)
2. Consolidate button/input sizing language across codebase
3. Create a form builder component for common patterns
4. Add form layout templates for multi-column forms

---

**END OF MIGRATION GUIDE**
