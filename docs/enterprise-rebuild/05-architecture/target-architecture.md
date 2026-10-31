# Target architecture - proposed, pending approval

Use a modular Django/DRF monolith with React/TypeScript frontend, PostgreSQL, controlled background jobs and a single authoritative service per business metric. This is proposed because the target business has a small technical/operations team; microservices are not justified by current evidence.

```mermaid
flowchart TB
  FE[React UI / typed API client] --> API[DRF API / authentication / object authorization]
  API --> LIC[Licence ledger service]
  API --> RULES[DFIA/SION restriction resolver]
  API --> TRADE[BOE / trade / document services]
  API --> REC[Operational reconciliation read model]
  API --> ACC[Accounting posting service]
  LIC --> DB[(PostgreSQL)]
  RULES --> DB
  TRADE --> DB
  REC --> DB
  ACC --> DB
  API --> JOB[Scoped background jobs]
  JOB --> DB
```

All services receive company context, validate object ownership and write immutable audit events for material actions. Accounting posting consumes approved business events, never draft screen opens.

