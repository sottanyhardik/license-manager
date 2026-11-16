# Mobile Optimization Guide

**For:** React/TypeScript License Manager SPA  
**Tailwind:** v4  
**Framework:** Vite + React 19.2

---

## Mobile-First Design Principles

### 1. Viewport & Responsive Breakpoints

Use Tailwind's built-in breakpoints:
```typescript
// Mobile first
sm: 640px
md: 768px
lg: 1024px
xl: 1280px
2xl: 1536px
```

For testing breakpoints:
- **390×844** (Mobile) - Default, design for this first
- **768×1024** (Tablet Portrait) - md: breakpoint
- **1024×768** (Tablet Landscape) - lg: breakpoint
- **1366×768** (Laptop) - xl: breakpoint
- **1440×900** (Desktop) - 2xl: breakpoint

### 2. Touch Target Sizing

**Minimum touch target: 44×44px**

```tsx
// Good - touch-friendly
<button className="h-11 w-11 rounded-md bg-blue-500">
  <Icon />
</button>

// Bad - too small for touch
<button className="h-6 w-6 rounded-md bg-blue-500">
  <Icon />
</button>
```

### 3. Font Sizing Strategy

```tsx
// Mobile-first scaling
<h1 className="text-2xl md:text-3xl lg:text-4xl">Title</h1>
<p className="text-sm md:text-base">Body text</p>
<button className="text-xs md:text-sm">Button text</button>
```

**Minimum readable:** 12px (14px preferred)  
**Line height:** 1.5 for body, 1.2 for headings

### 4. Spacing & Layout

```tsx
// Mobile-first stacking
<div className="flex flex-col md:flex-row gap-2 md:gap-4">
  {/* Stack on mobile, row on desktop */}
</div>

// Responsive padding
<div className="p-4 md:p-6 lg:p-8">
  {/* Smaller padding on mobile, larger on desktop */}
</div>
```

### 5. Navigation Patterns

#### Mobile Navigation
```tsx
// Use hamburger menu on mobile
<nav className="hidden md:flex">
  {/* Desktop menu */}
</nav>

<button className="md:hidden">
  {/* Mobile hamburger */}
</button>
```

#### Bottom Sheet for Mobile Actions
```tsx
// Actions drawer on mobile instead of top menu
<div className="md:hidden fixed bottom-0 left-0 right-0">
  {/* Mobile action sheet */}
</div>
```

### 6. Form Optimization for Mobile

```tsx
// Larger touch targets for forms
<input 
  className="h-11 px-3 py-2 text-base border rounded"
  // Use 16px minimum to avoid zoom on iOS
/>

// Full-width inputs on mobile
<input className="w-full md:w-1/2" />

// Stack labels above inputs
<div className="flex flex-col gap-2">
  <label>Name</label>
  <input />
</div>
```

### 7. Table Responsive Strategy

```tsx
// Option 1: Horizontal scroll on mobile
<div className="overflow-x-auto">
  <table>
    {/* Content */}
  </table>
</div>

// Option 2: Stack rows on mobile
<div className="flex flex-col md:flex-row">
  {data.map(item => (
    <div className="w-full md:w-1/3">
      {/* Card view on mobile */}
    </div>
  ))}
</div>
```

### 8. Modal & Dialogs

```tsx
// Full-screen on mobile, centered on desktop
<dialog className="
  fixed inset-0 md:inset-auto md:rounded-lg
  h-screen md:h-auto
  w-screen md:w-96
">
  {/* Content */}
</dialog>
```

### 9. Filter Components

```tsx
// Stack filters on mobile
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
  <FilterCard />
  <FilterCard />
  <FilterCard />
  <FilterCard />
</div>

// Or use mobile drawer
<button className="md:hidden">Show Filters</button>
```

### 10. Dark Mode Support

```tsx
// Use CSS variables for theme-aware colors
<div className="bg-white dark:bg-slate-950 text-black dark:text-white">
  {/* Content */}
</div>

// Tailwind's dark: prefix
<button className="bg-blue-500 dark:bg-blue-600">
  {/* Automatically switches in dark mode */}
</button>
```

---

## Responsive Testing Checklist

### Before Pushing Changes

- [ ] Test at 390×844 (mobile)
- [ ] Test at 768×1024 (tablet portrait)
- [ ] Test at 1024×768 (tablet landscape)
- [ ] No horizontal overflow at any breakpoint
- [ ] Touch targets >= 44×44px
- [ ] Text readable without pinch-zoom
- [ ] Forms functional on mobile keyboard
- [ ] Navigation accessible on mobile
- [ ] Tables don't overflow (or scroll smoothly)
- [ ] Dark mode colors have proper contrast
- [ ] Images responsive and not oversized

### Performance on Mobile

- [ ] Page loads in < 3 seconds on 4G
- [ ] No jank when scrolling
- [ ] Modals open smoothly
- [ ] Transitions don't block interactions

---

## Common Pitfalls

❌ **Hard-coded widths**
```tsx
<div style={{width: '1200px'}}>  // Bad on mobile!
```

✅ **Responsive widths**
```tsx
<div className="w-full md:w-3/4 lg:w-1/2">  // Good
```

---

❌ **Oversized touch targets**
```tsx
<button className="h-6 w-20">  // Too small
```

✅ **Touch-friendly sizes**
```tsx
<button className="h-11 px-4 py-2">  // Good
```

---

❌ **Fixed horizontal scroll**
```tsx
<table style={{minWidth: '1400px'}}>  // Forces scroll
```

✅ **Responsive tables**
```tsx
<div className="overflow-x-auto">
  <table>  {/* Content scrolls smoothly */}
```

---

❌ **Ignoring dark mode**
```tsx
<div className="bg-gray-100">  // Only light mode
```

✅ **Dark mode support**
```tsx
<div className="bg-gray-100 dark:bg-gray-900">
```

---

## Tools & Resources

### Testing Tools
- **Chrome DevTools:** F12 → Toggle Device Toolbar
- **Safari:** Develop → Enter Responsive Design Mode
- **Playwright:** Use `.viewportSize()` for automation
- **Manual Testing:** Test on real devices if possible

### Debugging
```bash
# Test responsive locally
cd frontend
npm run dev

# Open http://localhost:5173 in browser
# Press F12 → Toggle Device Toolbar
# Use keyboard shortcut: Cmd+Shift+M (Mac) or Ctrl+Shift+M (Windows)
```

### Resources
- [Tailwind CSS Responsive Design](https://tailwindcss.com/docs/responsive-design)
- [MDN: Responsive Design](https://developer.mozilla.org/en-US/docs/Learn/CSS/CSS_layout/Responsive_Design)
- [WCAG 2.1: Target Size](https://www.w3.org/WAI/WCAG21/Understanding/target-size.html)
- [Web.dev: Mobile Web Performance](https://web.dev/mobile/)

---

## Component Library Specifics

### shadcn/ui (Radix + Tailwind)

All shadcn/ui components are responsive by default if used correctly:

```tsx
// Button is touch-friendly by default
<Button>Action</Button>

// Dialog is mobile-responsive
<Dialog>
  <DialogContent>
    {/* Full-screen on mobile */}
  </DialogContent>
</Dialog>

// Input has proper sizing
<Input placeholder="Enter text" />
```

---

## Accessibility + Responsiveness

### Mobile Accessibility

1. **Focus indicators visible on mobile**
   ```tsx
   <button className="focus:outline-2 focus:outline-blue-500">
   ```

2. **Keyboard navigation works**
   - Tab order correct
   - Enter/Space triggers actions
   - Escape closes modals

3. **Screen reader friendly**
   - Labels associated with inputs
   - Buttons have text or aria-label
   - Semantic HTML structure

---

## Deployment Checklist

Before shipping responsive changes:

- [ ] All pages tested at 5 breakpoints
- [ ] No console errors on mobile
- [ ] Touch targets validated
- [ ] Dark mode verified
- [ ] Performance acceptable
- [ ] Accessibility tested (keyboard + screen reader)
- [ ] No horizontal overflow anywhere
- [ ] Form submission works on mobile

