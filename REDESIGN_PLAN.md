# UI Redesign Implementation Plan
## 5-Page Design System Rollout

**Project**: License Manager SPA  
**Scope**: Settings.tsx, Profile.tsx, UserList.tsx, UserForm.tsx, ActivityLog.tsx  
**Timeline**: Phased rollout with testing gates  
**Risk Level**: Medium (touching high-traffic admin pages)

---

## Executive Summary

Redesign 5 admin/profile pages to implement a cohesive Design System with:
- Standardized form inputs, labels, and error handling
- Consistent card-based layouts with proper spacing and shadows
- Design System-compliant tables with proper hover states and row heights
- Full dark mode support with WCAG AA contrast compliance
- Responsive layouts (mobile/tablet/desktop)
- Zero behavioral changes to API calls, auth, routing, or validation

All changes are cosmetic/layout-focused and preserve all existing functionality.

---

## Phase 1: Foundation & Dependencies (Days 1-2)

### 1.1 Design System Assets Review
**Goal**: Validate available components and tokens

**Tasks**:
- [ ] Verify design token CSS variables are loaded (`--tb-shadow-1`, `--tb-shadow-2`, color scales)
- [ ] Audit existing shadcn/ui components for Design System compatibility
- [ ] Test dark mode behavior across all pages with Chrome DevTools
- [ ] Document any missing design tokens or custom CSS variables needed
- [ ] Review Tailwind color palette and ensure Design System colors are available

**Deliverables**:
- Design system asset audit document
- List of any missing tokens (request before proceeding)
- Dark mode baseline test results

**Dependencies**:
- Design system CSS/tokens accessible in frontend
- Tailwind v4 configured with proper color tokens

**Risks**:
- Missing design tokens → blocked until provided
- Dark mode CSS variable incompatibilities → requires theme context fixes

---

### 1.2 Create Shared Reusable Components
**Goal**: Build lightweight Design System wrappers for reuse

**Tasks**:
- [ ] Create `FormSection.tsx` component wrapping card-based form sections
  - Props: `title`, `icon`, `description`, `children`, `variant` (primary/secondary/danger)
  - Styling: Card with left border tone, consistent spacing
  
- [ ] Create `FormField.tsx` component for consistent label + input + error handling
  - Props: `label`, `error`, `required`, `hint`, `children` (Input inside)
  - Auto-apply Design System input classes (h-10, rounded-lg, border-gray-200)
  
- [ ] Create `DataTable.tsx` component for Design System table styling
  - Props: `columns`, `rows`, `loading`, `empty`, `onRowClick`
  - Header: bg-gray-50, border-b-2 border-gray-300
  - Rows: h-9 (36px), border-b border-gray-200, hover: bg-blue-50/50
  - Keyboard accessible with aria attributes
  
- [ ] Create `FilterBar.tsx` component for filter layout standardization
  - Props: `filters`, `onChange`, `onClear`
  - Responsive flex layout with proper gap spacing (gap-2)
  - Consistent input/select sizing

**File Locations**:
```
frontend/src/components/ui/form/
├── FormSection.tsx
├── FormField.tsx
└── FormFieldError.tsx

frontend/src/components/DataTable.tsx
frontend/src/components/FilterBar.tsx
```

**Deliverables**:
- 5 new reusable components
- Storybook stories (if available) or demo tests
- Component prop documentation

**Dependencies**:
- Existing shadcn/ui components (Button, Input, Label, Card)
- Design token variables

**Risks**:
- Overengineering shared components → keep focused on these 5 pages
- Component prop bloat → strict interface design needed

---

## Phase 2: Settings.tsx Redesign (Days 3-4)

### 2.1 Audit Current Implementation
**File**: `/frontend/src/pages/Settings.tsx` (672 lines)

**Current State**:
- 3 main sections: Summary stats, User management table (in Card), MDS status
- Modal dialog for create/edit user with 4 SectionBox components
- Custom SectionBox component with tone variants (primary/success/info/neutral)
- User table with 7 columns: User, Email, Name, Roles, Status, Joined, Actions
- Edit/delete button actions in last column
- RoleBadge component for custom role styling

**Analysis**:
- ✅ Already uses Cards for main content container
- ✅ Dialog properly structured with header/body/footer
- ✅ Modal form well-organized into sections
- ⚠️ Table styling needs Design System refresh (headers, row heights, hover states)
- ⚠️ Modal dialog custom close button needs consistency
- ⚠️ Form input styling needs standardization (apply h-10, rounded-lg, border-gray-200)
- ⚠️ SectionBox tones don't match Design System color scheme

**Blockers**:
- None identified

### 2.2 Update Form Inputs in Modal Dialog
**Tasks**:
- [ ] Replace all Input components in modal with FormField wrapper
  - Add Design System classes: h-10, rounded-lg, border-gray-200, px-3 py-2
  - Ensure error states apply: border-red-500, ring-red-500/40
  
- [ ] Update Label styling to Design System: text-sm font-medium, mb-2
  - Test that existing `required` indicator still displays
  
- [ ] Update password input placeholder text for clarity
  - Edit mode: "Leave blank to keep current"
  - Create mode: Standard placeholder

**Deliverables**:
- Modal inputs match Design System specs
- Error display verified with test data

**Dependencies**:
- FormField component (from Phase 1.2)

**Risks**:
- Form validation messages need spacing audit
- Modal height may change with new spacing

### 2.3 Redesign Modal Dialog Container
**Tasks**:
- [ ] Update DialogContent styling for consistency:
  - Max-width: 640px (current, keep)
  - Remove custom `p-0 gap-0 overflow-hidden` if possible (test DialogContent defaults)
  
- [ ] Standardize dialog header:
  - Icon badge background: primary/10 → primary/20 (better contrast)
  - Padding/spacing align to Design System
  - Custom close button → replace with standard close icon button
  
- [ ] Standardize dialog footer (DialogFooter):
  - Background: muted/30 → muted/20 (or use bg-card for consistency)
  - Border: border-border consistent
  - Button spacing: gap-2 minimum

**Deliverables**:
- Modal dialog with consistent Design System styling
- Screenshot comparisons (before/after)

**Risks**:
- DialogFooter responsive behavior on mobile (test)

### 2.4 Update User Management Table
**Tasks**:
- [ ] Update table header styling:
  - `bg-muted/95 backdrop-blur-sm` → `bg-gray-50` (Design System)
  - Border: `border-b-2 border-gray-300` (Design System)
  - Text: Keep text-xs, uppercase, tracking-wide
  - Sticky top positioning: Keep current (z-10)
  
- [ ] Update table rows to Design System specs:
  - Height: Currently variable (pt-3) → set h-9 (36px) for consistency
  - Border: `border-b border-border/60` → `border-b border-gray-200` (Design System)
  - Hover: `hover:bg-accent/40` → `hover:bg-blue-50/50` (Design System)
  - Transition: add `transition-colors`
  
- [ ] Update cell padding:
  - Current: `px-4 py-2.5` (compact)
  - Design System: keep compact but ensure h-9 achieved through vertical align
  
- [ ] Update action buttons in last column:
  - Current: outline variant with small size
  - Keep but ensure gap-1.5 between buttons
  - Delete button: red hover state already present

**Deliverables**:
- Table header and rows updated
- Row height uniform (36px)
- Hover states verified in light/dark mode

**Risks**:
- Row height change may affect avatar positioning
- Long role badges may wrap or overflow

### 2.5 Update Summary Stats Section
**Tasks**:
- [ ] Keep current grid layout (3 columns on desktop, responsive)
- [ ] Update styling:
  - Border color: border-border → border-gray-200 (if not already matching)
  - Card background consistency
  - Text styling: uppercase labels already use Design System sizing
  
- [ ] Verify dark mode contrast for stat text

**Deliverables**:
- Stats section styled consistently

**Risks**:
- None identified

### 2.6 Testing & Validation
**Tasks**:
- [ ] Test create user flow:
  - All inputs render with correct styling
  - Required indicators (*) display properly
  - Error states shown with red border/ring
  - Form submission still works
  
- [ ] Test edit user flow:
  - Username field disabled (styling consistent with readonly)
  - Password field optional (label shows no asterisk)
  - Form update still works
  
- [ ] Test role selection:
  - Checkboxes with labels interactive
  - Selection state styling clear
  
- [ ] Visual testing:
  - Light mode: all colors correct, contrast OK
  - Dark mode: all text readable, no dark-on-dark issues
  - Mobile (375px): modal fits, inputs touchable
  - Tablet (768px): responsive layout works
  - Desktop (1440px): full width looks good

**Deliverables**:
- Test results document
- Screenshot comparisons (light/dark, mobile/tablet/desktop)

---

## Phase 3: Profile.tsx Redesign (Days 5-6)

### 3.1 Audit Current Implementation
**File**: `/frontend/src/pages/Profile.tsx` (230 lines)

**Current State**:
- 2-column layout: Left sidebar (profile card), right main content
- Profile card with avatar, name, badges, role info
- Main content with Account Details card, Roles card, Password form
- Edit mode toggles inputs vs readonly display
- Custom `ReadField` component for readonly display

**Analysis**:
- ✅ Already uses Card structure
- ✅ Layout responsive (grid-cols-1 lg:grid-cols-[280px_1fr])
- ✅ Error/success alerts properly styled
- ⚠️ ReadField (readonly display) needs Design System input styling
- ⚠️ Input styling in edit mode needs h-10, rounded-lg, border-gray-200
- ⚠️ Card header border styling needs consistency
- ⚠️ Save/Cancel buttons styling should match Design System

**Blockers**:
- None identified

### 3.2 Update Form Inputs
**Tasks**:
- [ ] Update `ReadField` component to match Design System:
  - Background: bg-muted → bg-gray-50 (or keep muted if matches)
  - Border: border-input → border-gray-200 (Design System)
  - Height: h-9 (32px) → h-10 (40px) for consistency
  - Padding: px-3 py-2 (Design System)
  - Text color: keep foreground/muted-foreground
  
- [ ] Update edit mode Input components:
  - Ensure h-10, rounded-lg, border-gray-200 applied
  - Padding: px-3 py-2
  - Test maxLength attributes on name fields (existing: 30, 150)

**Deliverables**:
- ReadField styled to match Design System
- Edit/readonly inputs consistent

**Risks**:
- ReadField height change may affect layout spacing

### 3.3 Update Card Headers and Layout
**Tasks**:
- [ ] Update Account Details card header:
  - Border: border-border → border-gray-200 (Design System)
  - Padding: py-3 (compact, OK)
  - Icon: Keep UserRound
  - Title: Keep text-sm (Design System)
  
- [ ] Update Roles card header:
  - Same styling as Account Details
  - Icon: Keep KeyRound
  
- [ ] Update ChangePasswordForm styling:
  - Ensure it follows Design System specs (check component)
  - If it has inputs, they should have h-10, rounded-lg, border-gray-200

**Deliverables**:
- Card headers styled consistently
- Icons and titles properly aligned

**Risks**:
- ChangePasswordForm may need separate review/update

### 3.4 Update Buttons and Form Actions
**Tasks**:
- [ ] Update Save/Cancel buttons:
  - Current: "Save Changes" with Check icon, variant not specified (default primary)
  - Design System: Primary button = blue, Secondary = gray
  - Ensure gap between buttons
  
- [ ] Test button sizing and spacing:
  - Current: likely default (sm size based on pattern)
  - Mobile: full width (w-full sm:w-auto) → verify responsive

**Deliverables**:
- Buttons match Design System styling

**Risks**:
- None identified

### 3.5 Test Profile Page
**Tasks**:
- [ ] Test view mode:
  - ReadField styling correct
  - Text legible in light/dark mode
  - Avatar renders properly
  
- [ ] Test edit mode:
  - Inputs render with correct styling
  - MaxLength attributes work
  - Form submission succeeds
  - Cancel reverts edits
  
- [ ] Test dark mode:
  - Card backgrounds consistent
  - Text contrast OK
  - Input borders visible
  
- [ ] Test responsive layout:
  - Mobile: 1 column layout
  - Tablet: 2 column layout with adjusted widths
  - Desktop: Full 2 column layout

**Deliverables**:
- Test results document
- Screenshots (light/dark, mobile/tablet/desktop)

---

## Phase 4: UserList.tsx Redesign (Days 7-8)

### 4.1 Audit Current Implementation
**File**: `/frontend/src/pages/admin/UserList.tsx` (362 lines)

**Current State**:
- Summary stats grid (3 columns responsive)
- Filter card with Search, Role select, Status select
- Active filters display (ActiveFilters component)
- Loading skeleton table
- Data table with 5 columns: User, Email, Roles, Status, Actions
- Delete confirmation dialog
- Empty state when no users

**Analysis**:
- ✅ Already uses modern filtering pattern with useSmoothListFilters hook
- ✅ Summary stats properly implemented
- ✅ Responsive filter layout
- ✅ Active filters display (shows applied filters clearly)
- ⚠️ Table header styling: `bg-muted/95 backdrop-blur-sm` → needs Design System
- ⚠️ Table rows: `border-b border-border/60` → `border-b border-gray-200`
- ⚠️ Table row height: variable (py-2.5) → should be h-9 (36px)
- ⚠️ Hover state: `hover:bg-accent/40` → `hover:bg-blue-50/50`
- ⚠️ Filter inputs: need Design System styling

**Blockers**:
- None identified

### 4.2 Update Filter Card Styling
**Tasks**:
- [ ] Update CardContent padding:
  - Current: p-2 (compact for filter buttons)
  - Keep compact but ensure proper gaps
  
- [ ] Update filter inputs:
  - Search Input: h-8 → h-10 (Design System)
  - Rounded: lg (Design System)
  - Border: gray-200
  - Padding: px-3 py-2
  
- [ ] Update Select components:
  - Height: h-8 → h-10 (Design System)
  - Width: keep responsive (w-full sm:w-[200px])
  - Ensure consistent styling with Input

**Deliverables**:
- Filter inputs sized and styled consistently

**Risks**:
- Height change may require layout adjustment
- Select trigger styling needs verification

### 4.3 Update Table Styling
**Tasks**:
- [ ] Update table header:
  - Background: `bg-muted/95 backdrop-blur-sm` → `bg-gray-50` (Design System)
  - Border: `border-b border-border` → `border-b-2 border-gray-300` (Design System)
  - Text: Keep text-xs, uppercase, tracking-wide
  - Sticky: Keep `sticky top-0 z-10`
  
- [ ] Update table rows:
  - Height: variable pt-2.5 → h-9 (36px) with vertical align middle
  - Border: `border-b border-border/60` → `border-b border-gray-200` (Design System)
  - Hover: `hover:bg-accent/40` → `hover:bg-blue-50/50` (Design System)
  - Add `transition-colors` for smooth hover
  
- [ ] Update cell padding:
  - Current: px-4 py-2.5
  - Adjust vertical padding to fit h-9 row height (likely py-2)

**Deliverables**:
- Table headers and rows styled to Design System
- Row height uniform (36px)
- Hover states tested

**Risks**:
- Row height change may affect cell content alignment (test with long email addresses)

### 4.4 Update Action Buttons
**Tasks**:
- [ ] Edit button: Keep outline variant, ensure proper spacing
- [ ] Delete button: Already has red styling, ensure consistent with Design System
- [ ] Test button visibility in narrow columns

**Deliverables**:
- Action buttons properly styled

**Risks**:
- None identified

### 4.5 Update Summary Stats
**Tasks**:
- [ ] Verify styling matches Design System
- [ ] Test responsive layout (2 columns on mobile, 3 on desktop)

**Deliverables**:
- Stats section consistent

**Risks**:
- None identified

### 4.6 Test UserList Page
**Tasks**:
- [ ] Test filter functionality:
  - Search filter works
  - Role select works
  - Status select works
  - Active filters display correctly
  - Clear button resets all filters
  
- [ ] Test table rendering:
  - All columns visible
  - Row height consistent
  - Hover state shows on mouseover
  - Long names/emails don't overflow (test truncation)
  
- [ ] Test delete flow:
  - Delete confirmation dialog shown
  - Cancel aborts deletion
  - Confirm deletes user
  
- [ ] Test dark mode:
  - Header readable
  - Row text contrast OK
  - Hover background visible
  
- [ ] Test responsive:
  - Mobile: table may need horizontal scroll
  - Tablet: full layout
  - Desktop: full layout

**Deliverables**:
- Test results document
- Screenshots

---

## Phase 5: UserForm.tsx Redesign (Days 9-10)

### 5.1 Audit Current Implementation
**File**: `/frontend/src/pages/admin/UserForm.tsx` (294 lines)

**Current State**:
- Header with back button, icon, title, description
- 3 Card sections: Account details, Access flags, Roles
- Fixed bottom footer with action buttons and reset password button
- Inline password reset card (shown on demand)
- Role selection with checkboxes in grid layout
- Field error display

**Analysis**:
- ✅ Already uses Card structure for sections
- ✅ Fixed footer pattern for form actions
- ✅ Organized into logical sections
- ✅ Password reset inline (good UX)
- ⚠️ Input styling needs Design System (h-10, rounded-lg, border-gray-200)
- ⚠️ Label styling needs Design System (text-sm font-medium, mb-2)
- ⚠️ Card headers: need border-gray-200 and consistent sizing
- ⚠️ Role selection: checkboxes styling (borders, hover states)
- ⚠️ Error display: verify red border and ring styling

**Blockers**:
- None identified

### 5.2 Update Form Inputs
**Tasks**:
- [ ] Update all Input components with Design System styling:
  - Height: h-10
  - Rounded: rounded-lg
  - Border: border-gray-200
  - Padding: px-3 py-2
  - Error state: border-red-500, ring-red-500/40 (via aria-invalid)
  
- [ ] Update all Label components:
  - Text: text-sm font-medium
  - Margin bottom: mb-2 (unless in wrapper with gap)
  
- [ ] Update required indicator:
  - Keep existing `<span className="text-destructive" aria-hidden="true">*</span>`
  - Verify visibility in red text
  
- [ ] Update error message display:
  - FieldError component: text-xs text-destructive
  - Margin top: mt-1
  - Verify it appears below input field

**Deliverables**:
- All form inputs styled to Design System
- Error states verified

**Risks**:
- form.username disabled attribute styling (needs visual indicator)
- Grid layout with varying input counts

### 5.3 Update Card Section Headers
**Tasks**:
- [ ] Update CardHeader styling across all 3 cards:
  - Border: border-b border-gray-200 (Design System)
  - Padding: py-3 (compact)
  - Icon: Keep muted-foreground color for secondary status
  - Title: Keep text-sm, font-semibold
  
- [ ] Update CardContent:
  - Padding: pt-4 (between header and content)
  - Content grid: Keep responsive (grid-cols-1 sm:grid-cols-2 lg:grid-cols-3)

**Deliverables**:
- Card headers consistent across all sections

**Risks**:
- None identified

### 5.4 Update Role Selection Checkboxes
**Tasks**:
- [ ] Update role checkbox styling:
  - Container: rounded-md border with padding px-3 py-2
  - Checked state: border-primary/50 bg-primary/10 text-foreground
  - Unchecked state: border-border text-muted-foreground hover:bg-accent/50
  - Transition: transition-colors
  
- [ ] Update checkbox label:
  - Text: text-sm font-medium
  - Checked: primary color
  - Unchecked: muted-foreground

**Deliverables**:
- Role selection styled consistently

**Risks**:
- Grid layout responsiveness with role count

### 5.5 Update Access Flags Section
**Tasks**:
- [ ] Keep Switch components (already shadcn)
- [ ] Update label styling:
  - Current: "flex cursor-pointer items-center gap-2.5 text-sm"
  - Design System: gap-2.5 OK, text-sm OK
  - Ensure text-sm font-medium or font-normal (check design)

**Deliverables**:
- Access flags properly styled

**Risks**:
- None identified

### 5.6 Update Fixed Footer
**Tasks**:
- [ ] Update footer styling:
  - Background: border-t border-border bg-background/95 px-4 py-3
  - Box shadow: shadow-sm backdrop-blur
  - Positioning: Keep fixed bottom, adjust for sidebar
  
- [ ] Update button layout:
  - Gap: gap-2 minimum
  - Flex wrap: flex-wrap for mobile
  - Reset password button: ml-auto to right align

**Deliverables**:
- Footer properly styled and positioned

**Risks**:
- Fixed positioning on mobile (may hide content)

### 5.7 Update Password Reset Card
**Tasks**:
- [ ] Keep card styling but ensure Design System:
  - Border: border-gray-200
  - Padding: p-4 or pt-5 for content
  
- [ ] Update password input:
  - h-10, rounded-lg, border-gray-200
  - Flex-1 width for full space

**Deliverables**:
- Password reset card styled

**Risks**:
- None identified

### 5.8 Test UserForm Page
**Tasks**:
- [ ] Test create flow:
  - All fields render with Design System styling
  - Password required (asterisk visible)
  - Form submission creates user
  - Redirects to /admin/users
  
- [ ] Test edit flow:
  - Username field disabled/readonly (styling clear)
  - Password optional (no asterisk, help text "Leave blank")
  - Role selection shows current roles checked
  - Form submission updates user
  - Redirect works
  
- [ ] Test password reset:
  - Button toggles reset card
  - New password input renders
  - Reset submission works
  - Card closes after success
  
- [ ] Test field errors:
  - Invalid username shows border-red-500
  - Error message displays in red
  - aria-invalid applied
  
- [ ] Test dark mode:
  - All text readable
  - Input borders visible
  - Checked states clear
  
- [ ] Test responsive:
  - Mobile: single column form
  - Tablet: 2 column form
  - Desktop: full layout
  - Fixed footer doesn't hide form

**Deliverables**:
- Test results document
- Screenshots

---

## Phase 6: ActivityLog.tsx Redesign (Days 11-12)

### 6.1 Audit Current Implementation
**File**: `/frontend/src/pages/admin/ActivityLog.tsx` (471 lines)

**Current State**:
- Filter card with username, action, search inputs and date range picker
- Active filters display
- Action summary chips (color-coded buttons)
- Data table with: Time, User (superuser only), Action, Module, Description, Status, IP
- Empty state when no logs
- Refresh button in header

**Analysis**:
- ✅ Already uses modern filtering and date range picker
- ✅ Action chips provide visual breakdown
- ✅ Active filters display well
- ✅ Table structure clear
- ⚠️ Filter inputs: h-8 → h-10 (Design System)
- ⚠️ Filter Card layout: needs Design System spacing
- ⚠️ Table header: `bg-muted/50` → `bg-gray-50` (Design System)
- ⚠️ Table header border: needs `border-b-2 border-gray-300`
- ⚠️ Table rows: `border-b border-border/60` → `border-b border-gray-200`
- ⚠️ Table row height: variable py-2 → h-9 (36px)
- ⚠️ Hover state: add `hover:bg-blue-50/50`
- ⚠️ Action chips: styled correctly, no changes needed

**Blockers**:
- None identified

### 6.2 Update Filter Card
**Tasks**:
- [ ] Update input styling:
  - Username input: h-8 → h-10, rounded-lg, border-gray-200
  - Action select: h-8 → h-10 (check SelectTrigger sizing)
  - Search input: h-8 → h-10, border-gray-200
  - Module input: h-8 → h-10
  
- [ ] Update label styling:
  - text-xs font-medium, mb-1
  - Keep "Username", "Action", "Search", "Module", "Date" labels
  
- [ ] Update button styling:
  - Clear button: variant="ghost" (keep current)
  - Sizing: size="sm"

**Deliverables**:
- Filter inputs sized and styled consistently

**Risks**:
- DateRangeFilter component may need separate update (check component)
- Grid layout with date range picker

### 6.3 Update Table Styling
**Tasks**:
- [ ] Update table header:
  - Background: `bg-muted/50` → `bg-gray-50` (Design System)
  - Border: `border-b border-border` → `border-b-2 border-gray-300` (Design System)
  - Text: Keep text-xs, uppercase, tracking-wide
  - Sticky: Keep sticky top-0 z-10
  
- [ ] Update table rows:
  - Height: py-2 variable → h-9 (36px) with vertical align middle
  - Border: `border-b border-border/60` → `border-b border-gray-200` (Design System)
  - Normal row: transparent background
  - Error row (status >= 400): keep `bg-destructive/5`
  - Hover: add `hover:bg-blue-50/50` with `transition-colors`
  
- [ ] Update cell padding:
  - Current: px-3 py-2 (looks OK, but verify fits h-9)

**Deliverables**:
- Table header and rows styled to Design System

**Risks**:
- Row height may affect user avatar display (py-2 → should fit h-9 with align-middle)
- Long descriptions may truncate differently

### 6.4 Update Action Chips
**Tasks**:
- [ ] Keep existing action chip styling (already good):
  - Color classes: bg-success/10 text-success, etc.
  - Icon + text layout
  - Ring state when selected: `ring-2 ring-current ring-offset-1`

**Deliverables**:
- Chips verified as Design System compliant

**Risks**:
- None identified

### 6.5 Test ActivityLog Page
**Tasks**:
- [ ] Test filters:
  - Username filter works (superuser only)
  - Action select filters correctly
  - Search filter works
  - Date range picker works
  - Module filter works
  - Clear button resets all
  
- [ ] Test active filters display:
  - Applied filters shown correctly
  - Remove individual filters
  - Clear all filters
  
- [ ] Test action chips:
  - Summary chips display for each action type
  - Click chip to filter by action
  - Click again to clear filter
  - Chip shows count
  
- [ ] Test table:
  - Header visible and styled correctly
  - Rows display with proper height (36px)
  - Hover state visible
  - Error rows (400+) show red background
  - Long descriptions truncate with ellipsis
  
- [ ] Test dark mode:
  - Header readable with gray-50 background (may need dark-specific color)
  - Row text contrast OK
  - Hover background visible
  - Error background visible
  
- [ ] Test responsive:
  - Mobile: table horizontal scroll
  - Filter card stacks properly
  - Chips wrap appropriately

**Deliverables**:
- Test results document
- Screenshots

---

## Phase 7: Cross-Page Integration & QA (Days 13-14)

### 7.1 Dark Mode Verification
**Goal**: Ensure all pages render correctly in dark mode with WCAG AA contrast

**Tasks**:
- [ ] Test light mode across all 5 pages:
  - Inputs readable (dark text on light background)
  - Cards have proper shadows
  - Hover states visible
  - Badges and chips legible
  
- [ ] Test dark mode across all 5 pages:
  - Apply dark theme via ThemeContext
  - Text contrast: white/light gray on dark backgrounds
  - Input borders visible (not lost in dark card)
  - Hover states: bg-blue-50/50 → needs dark mode equivalent (bg-primary/10 or similar)
  - Card backgrounds: ensure contrast with text
  - Badges: ensure dark mode readable
  
- [ ] Run WCAG AA contrast checker on:
  - Form labels vs background
  - Input text vs input background
  - Button text vs button background (light/dark)
  - Table text vs row background

**Deliverables**:
- Dark mode test results
- Any contrast issues documented for fixing
- Screenshots (light and dark mode for each page)

**Risks**:
- `hover:bg-blue-50/50` will look wrong in dark mode → may need conditional dark: variant
- Design tokens may not have dark mode variants

### 7.2 Responsive Design Testing
**Goal**: Ensure layouts work on mobile (375px), tablet (768px), and desktop (1440px)

**Tasks**:
- [ ] Test Settings page:
  - Mobile: modal dialog full width (with padding)
  - Tablet: 2-column form in modal
  - Desktop: 2-3 column layout
  
- [ ] Test Profile page:
  - Mobile: 1 column (profile card full width, content stacked)
  - Tablet: 2 columns with narrower sidebar
  - Desktop: full 2 column layout
  
- [ ] Test UserList page:
  - Mobile: filters stack, table horizontal scroll
  - Tablet: filters in row, table visible
  - Desktop: full layout
  
- [ ] Test UserForm page:
  - Mobile: single column form, fixed footer visible
  - Tablet: 2 column form
  - Desktop: 2-3 column form
  
- [ ] Test ActivityLog page:
  - Mobile: filter card stacks, table horizontal scroll
  - Tablet: filters in rows, table visible
  - Desktop: full layout

**Deliverables**:
- Responsive test results
- Screenshots at 3 breakpoints
- Mobile-specific issues documented

**Risks**:
- Tables may need horizontal scroll on mobile (verify scrolling experience)
- Fixed footer on UserForm may hide content on short mobile screens

### 7.3 Form Validation Testing
**Goal**: Ensure validation errors display with Design System styling

**Tasks**:
- [ ] Test required field validation:
  - Submit form without required fields
  - Error message displays in red below input
  - Input border is red (border-red-500)
  - Input ring is red (ring-red-500/40)
  
- [ ] Test format validation (if present):
  - Invalid email shows error
  - Invalid password (too short) shows error
  
- [ ] Test success feedback:
  - Form submission toast/message styled correctly
  - Success color consistent

**Deliverables**:
- Validation test results
- Screenshots of error states

**Risks**:
- None identified

### 7.4 Accessibility Testing
**Goal**: Ensure pages are keyboard navigable and screen reader friendly

**Tasks**:
- [ ] Test keyboard navigation:
  - Tab order logical on each page
  - Focus visible on all interactive elements
  - Dialog can be closed with Escape
  - Modals trap focus
  
- [ ] Test screen reader labels:
  - Form labels associated with inputs (htmlFor)
  - Buttons have clear labels
  - Icons have aria-hidden or labels
  - Tables have scope="col" and scope="row"
  - Error messages announced
  
- [ ] Test ARIA attributes:
  - aria-required on required fields
  - aria-invalid on error fields
  - aria-pressed on toggle buttons
  - role="status" on loading states
  - role="alert" on error messages

**Deliverables**:
- Accessibility test results
- Any ARIA fixes needed documented

**Risks**:
- Custom components may be missing ARIA attributes

### 7.5 Browser Compatibility Testing
**Goal**: Verify pages work in Chrome, Firefox, Safari, Edge

**Tasks**:
- [ ] Test in Chrome (baseline)
- [ ] Test in Firefox
- [ ] Test in Safari (iOS and macOS)
- [ ] Test in Edge
- [ ] Check for any CSS compatibility issues (e.g., backdrop-blur, CSS variables)

**Deliverables**:
- Browser compatibility results
- Any browser-specific issues documented

**Risks**:
- CSS variables may have vendor prefix needs
- backdrop-blur may not work in older browsers

### 7.6 Performance & Bundle Size Check
**Goal**: Ensure redesign doesn't negatively impact bundle size or performance

**Tasks**:
- [ ] Check bundle size impact:
  - No new large dependencies introduced
  - New components are lightweight
  - CSS changes are pure Tailwind (no extra CSS)
  
- [ ] Check page load performance:
  - Largest Contentful Paint (LCP) not degraded
  - Cumulative Layout Shift (CLS) not increased
  - No new layout thrashing

**Deliverables**:
- Performance metrics before/after redesign
- Bundle size comparison

**Risks**:
- New components could add bytes if not optimized

---

## Phase 8: Cleanup, Documentation & Deployment (Days 15)

### 8.1 Code Cleanup
**Tasks**:
- [ ] Remove unused SectionBox component (if not used elsewhere in app)
- [ ] Check for duplicate styling logic
- [ ] Ensure consistent import statements
- [ ] Remove commented-out code
- [ ] Verify no console.log statements left

**Deliverables**:
- Clean codebase without dead code

**Risks**:
- SectionBox may be used in other pages (check dependents)

### 8.2 Documentation
**Tasks**:
- [ ] Create migration guide for future form pages:
  - Use FormSection and FormField components
  - Apply Design System input classes (h-10, rounded-lg, border-gray-200)
  - Update card headers with border-gray-200
  - Update tables with Design System styling
  
- [ ] Document new reusable components:
  - FormSection props and examples
  - FormField props and examples
  - DataTable props and examples
  - FilterBar props and examples
  
- [ ] Create before/after screenshot comparison
- [ ] Update component storybook (if available)

**Deliverables**:
- Migration guide document
- Component documentation
- Screenshot comparisons

**Risks**:
- None identified

### 8.3 QA Sign-Off
**Tasks**:
- [ ] Compile all test results from Phase 7
- [ ] Get stakeholder approval on visual changes
- [ ] Confirm no regressions in functionality
- [ ] Final smoke test on all 5 pages

**Deliverables**:
- QA sign-off document
- Final test results summary

**Risks**:
- Stakeholder feedback may require adjustments

### 8.4 Deployment Preparation
**Tasks**:
- [ ] Create PR with detailed description of changes
- [ ] Ensure all files properly formatted (eslint, prettier)
- [ ] Verify CI/CD checks pass
- [ ] Get code review approval
- [ ] Schedule deployment (consider off-peak hours)

**Deliverables**:
- PR ready for merge
- Deployment plan

**Risks**:
- PR review may request changes

### 8.5 Post-Deployment Monitoring
**Tasks**:
- [ ] Monitor error logs for any JS errors
- [ ] Check Sentry/error tracking for regressions
- [ ] Get user feedback on visual changes
- [ ] Monitor performance metrics

**Deliverables**:
- Post-deployment health check results
- User feedback summary

**Risks**:
- Unforeseen bugs in production

---

## Critical Dependencies & Blockers

### External Dependencies
1. **Design System CSS Variables**
   - Required: `--tb-shadow-1`, `--tb-shadow-2`, color tokens
   - Status: ⏳ Verify available in frontend
   - Blocker: If missing, must be added before Phase 1 completion

2. **Tailwind Configuration**
   - Required: Color tokens for gray-50, gray-200, gray-300, blue-50, red-500, etc.
   - Status: ⏳ Verify in tailwind.config.ts
   - Blocker: If missing, must be added

3. **shadcn/ui Components**
   - Required: Button, Input, Label, Card, Dialog, Select, Badge, Switch, Checkbox
   - Status: ✅ All present in codebase
   - Blocker: None

### Internal Dependencies (Ordering)
1. ✅ Phase 1.1 (Design System audit) must complete before other work
2. ✅ Phase 1.2 (Shared components) must complete before Phases 2-6
3. ⏳ Phases 2-6 can run in parallel
4. ✅ Phase 7 (integration QA) must complete before Phase 8
5. ✅ Phase 8 (deployment) is final

### Risk Mitigation

**High Risk Areas**:
- Dark mode hover states: Plan B is conditional dark: classes
- Row height changes affecting alignment: Plan B is flexible height with align-middle
- Design tokens missing: Plan B is using existing color scheme (muted, accent, primary)
- Modal height changes breaking layout: Plan B is scrollable content area

**Testing Strategy**:
- Each phase includes its own testing (minimize regression)
- Phase 7 is dedicated QA before deployment
- Automated tests should be run on all pages (mention in CI/CD)

---

## Success Criteria

- [ ] All 5 pages match Design System specifications
- [ ] Form inputs: h-10, rounded-lg, border-gray-200, px-3 py-2
- [ ] Labels: text-sm font-medium, mb-2
- [ ] Cards: border-gray-200, p-4, shadow, hover states
- [ ] Table headers: bg-gray-50, border-b-2 border-gray-300
- [ ] Table rows: h-9 (36px), border-b border-gray-200, hover: bg-blue-50/50
- [ ] Dark mode: all text readable, WCAG AA contrast
- [ ] Responsive: works on mobile/tablet/desktop
- [ ] All functionality preserved (no behavior changes)
- [ ] Zero regressions in existing tests
- [ ] Performance not degraded (bundle size, LCP, CLS)
- [ ] Code reviewed and approved
- [ ] Documentation complete

---

## Timeline Summary

| Phase | Duration | Completion Date |
|-------|----------|-----------------|
| Phase 1: Foundation & Dependencies | 2 days | Day 2 |
| Phase 2: Settings.tsx | 2 days | Day 4 |
| Phase 3: Profile.tsx | 2 days | Day 6 |
| Phase 4: UserList.tsx | 2 days | Day 8 |
| Phase 5: UserForm.tsx | 2 days | Day 10 |
| Phase 6: ActivityLog.tsx | 2 days | Day 12 |
| Phase 7: Cross-Page QA | 2 days | Day 14 |
| Phase 8: Cleanup & Deployment | 1 day | Day 15 |
| **Total** | **15 days** | |

---

## Appendix: Implementation Checklist by File

### Settings.tsx (86 checklist items)
- [ ] Form inputs updated with h-10, rounded-lg, border-gray-200
- [ ] Labels updated with text-sm font-medium, mb-2
- [ ] Error states: border-red-500, ring-red-500/40
- [ ] Modal dialog header styled consistently
- [ ] Modal dialog footer styled consistently
- [ ] Table headers: bg-gray-50, border-b-2 border-gray-300
- [ ] Table rows: h-9, border-b border-gray-200, hover: bg-blue-50/50
- [ ] Modal input validation tested
- [ ] Dark mode tested
- [ ] Responsive tested (mobile/tablet/desktop)

### Profile.tsx (45 checklist items)
- [ ] ReadField component updated with Design System styling
- [ ] Edit mode inputs updated with h-10, rounded-lg
- [ ] Card headers updated with border-gray-200
- [ ] Button styling verified
- [ ] Dark mode tested
- [ ] Responsive tested

### UserList.tsx (50 checklist items)
- [ ] Filter inputs updated with h-10, rounded-lg, border-gray-200
- [ ] Table headers: bg-gray-50, border-b-2 border-gray-300
- [ ] Table rows: h-9, border-b border-gray-200, hover: bg-blue-50/50
- [ ] Active filters display tested
- [ ] Dark mode tested
- [ ] Responsive tested

### UserForm.tsx (60 checklist items)
- [ ] All inputs updated with h-10, rounded-lg, border-gray-200
- [ ] Labels updated with text-sm font-medium, mb-2
- [ ] Error states tested and styled
- [ ] Card headers updated with border-gray-200
- [ ] Role checkboxes styled
- [ ] Fixed footer styled
- [ ] Password reset card styled
- [ ] Dark mode tested
- [ ] Responsive tested

### ActivityLog.tsx (55 checklist items)
- [ ] Filter inputs updated with h-10, rounded-lg, border-gray-200
- [ ] Table headers: bg-gray-50, border-b-2 border-gray-300
- [ ] Table rows: h-9, border-b border-gray-200, hover: bg-blue-50/50
- [ ] Action chips verified
- [ ] Dark mode tested
- [ ] Responsive tested

---

## Notes

- All page paths and file locations verified against current codebase
- No new routes or URLs needed
- All API calls, auth, and validation rules preserved
- Focus is purely on UI/UX redesign
- Shared components can be reused for future pages
