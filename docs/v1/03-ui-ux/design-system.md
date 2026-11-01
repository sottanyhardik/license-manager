# V1 design system

**Proposed for V1; reuse current Tailwind 4 + Radix/shadcn stack.** No new component library is justified.

| Area | Contract |
| --- | --- |
| Shell | Responsive role-filtered navigation, command palette, skip link, focus return on drawer close, contextual quick actions. |
| Typography/spacing | Tokenized semantic scale; no one-off Bootstrap utilities in new/changed work. |
| Forms | Label, help, required/format feedback, server error summary, dirty/submit protection, explicit destructive confirmation. |
| Dense data | Semantic columns and aligned decimals; filters/sort/pagination in URL or saved view; exports show applied filters and generation time. |
| States | Skeleton for known shape; explanatory empty state; permission-denied state; retryable error; non-blocking success/error toast. |
| Accessibility | WCAG 2.2 AA target; keyboard reachability, visible focus, correct dialog semantics, labelled controls, non-colour status, 44px touch targets where touch-primary. |
| Responsive | Preserve financial table columns on desktop; switch to purpose-designed summaries on small screens instead of accidental cardification. |

Shared primitives own tokens and behavior; feature modules own domain wording, columns and workflow variants.
