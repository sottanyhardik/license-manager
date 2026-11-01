# Information architecture

**Proposed for V1.** Navigation follows work rather than model names:

```mermaid
flowchart TD
  Home[Overview] --> Licences[Licences & balances]
  Licences --> Planning[Planning & allotments]
  Imports[Imports / BOEs] --> Planning
  Trade[Trade & documents] --> Reconcile[BOE / invoice reconciliation]
  Licences --> Reports[Ledgers, reports & exports]
  Admin[Administration] --> Masters[Master data]
  Admin --> Users[Users & roles]
```

Route registry becomes the sole declarative source for navigation labels, feature role hints, breadcrumbs, icons and route metadata. API authorization is not derived from it. Page headers expose one primary action, contextual secondary actions, saved filters where useful, and a visible data/provenance timestamp for financial surfaces.
