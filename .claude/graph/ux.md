# 📱 UX Role

**Purpose:** navigation, responsiveness, accessibility, and state coverage.

## Mandate
- Every async surface has **loading / error / empty / success** states.
  Loading → `skeleton` primitive; feedback → `sonner` toasts (migrate away from
  `react-toastify`).
- Mobile-first responsive: verify at sm/md/lg/xl breakpoints.
- Keyboard navigable; visible focus rings; logical tab order.
- Command palette (`cmdk`, Cmd+K) and routing (`react-router-dom` v7) remain
  consistent across pages.
- Forms: clear inline validation/error handling (see repo's
  `FORM_ERROR_HANDLING.md` / `frontend/FORM_ERROR_HANDLING.md`).

## Checklist
- [ ] Loading/error/empty states present
- [ ] Reachable and operable by keyboard
- [ ] ARIA roles/labels where Radix doesn't already provide them
- [ ] No layout break at 360px / 768px / 1024px / 1440px
- [ ] Back-navigation behaves (see `BACK_NAVIGATION.md`)

## Exit criteria
No dead-end states; no keyboard trap; responsive at all breakpoints.
