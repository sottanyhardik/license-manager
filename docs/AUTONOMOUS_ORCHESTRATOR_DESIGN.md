# Autonomous License Manager Modernization Orchestrator
**Design & Architecture**  
**Date:** 2026-08-10  
**Status:** Active Implementation

---

## 1. STATE MACHINE

### Global States
```
INITIALIZE → DISCOVER → PLAN → EXECUTE → VERIFY → FREEZE → NEXT → AUDIT → RELEASE
```

### Module States (per module)
```
DISCOVERY → DESIGN → BUSINESS_GATE → GOLDEN_DATA → CHARACTERIZATION →
IMPLEMENTATION → MIGRATION → RUNTIME_VERIFY → SECURITY → PERFORMANCE →
PARITY → LEGACY_CLEANUP → ADVERSARIAL → FREEZE → (FROZEN | BLOCKED)
```

### Agent States
```
QUEUED → RUNNING → WAITING → COMPLETED → (FAILED | BLOCKED | CANCELLED)
```

---

## 2. CORE COMPONENTS

### State Files (docs/orchestrator/)
- `state.json` — Global program state
- `modules.json` — Per-module state
- `agents.json` — Agent registry
- `locks.json` — Write lock tracking
- `gates.json` — Gate pass/fail records
- `blockers.json` — Active blockers
- `dependency_graph.json` — Module dependencies
- `checkpoints/` — Recovery checkpoints

### Safety Systems
- **Write Lock Engine** — One writer per production scope
- **Dependency Scheduler** — Modules ordered by dependencies
- **Evidence Collector** — Runtime test capture
- **Gate Validator** — Pass/fail decision logic
- **Git Safety** — Protected files, scope verification
- **Crash Recovery** — Checkpoint-based resume

### Agent System
- **Agent Registry** — Role, state, lock, evidence
- **Role Templates** — Specialist definitions
- **Task Generation** — Dynamic prompt from module context
- **Evidence Persistence** — audit_evidence/ directory

---

## 3. GATE REQUIREMENTS

### Discovery Gate
```
Requires:
- MODULE_X_BASELINE.md
- MODULE_X_BUSINESS_RULES.md
- MODULE_X_CALCULATIONS.md
- MODULE_X_DATA_INTEGRITY.md
- MODULE_X_DEPENDENCIES.md
- MODULE_X_TEST_INVENTORY.md
- MODULE_X_RISK_REGISTER.md

Pass: All files exist and have substantive content
Fail: Missing or empty files
Blocked: Semantic ambiguity (mark with "UNKNOWN", "AMBIGUOUS", or "CONFLICTING")
```

### Business Semantics Gate
```
For financial modules:
- Formula documented with inputs/outputs
- Precision rule explicit
- Rounding rule explicit
- Edge cases documented
- Canonical owner identified

Pass: All clear
Blocked: Any UNKNOWN or CONFLICTING
Action: BLOCKED (do not invent values)
```

### Golden Test Gate
```
Requires: MODULE_X_GOLDEN_SCENARIOS.md

Pass: All scenarios run, all differences == 0
Fail: Any difference != 0 (unless approved semantic change documented)
Blocked: Cannot run tests (environment issue, missing test file)
```

### Implementation Gate
```
Requires: Discovery, Design, Business, Golden, Characterization all PASS

Then: Acquire write lock for module scope
Status: IMPLEMENTING
```

### Runtime Test Gate
```
Requires: exit_code == 0 for all:
- unit tests
- integration tests
- golden tests
- regression tests

Pass: All pass
Fail: Any failure
Blocked: Environment cannot be recovered
```

### Adversarial Gate
```
Requires: Minimum 2 independent reviews
- Calculation audit
- Database integrity
- Security audit
- Parity audit
- Performance audit (if applicable)

Pass: All agree, no critical issues
Blocked: Disagreement or critical issues found
Action: Must resolve before freeze
```

### Parity Gate
```
For financial values:
- API value == CANONICAL
- PDF value == CANONICAL
- EXCEL value == CANONICAL
- Reports == CANONICAL

Pass: 100% match
Blocked: Any difference (investigate and fix)
```

### Freeze Gate
```
All gates above PASS
Write lock can be released
Module marked FROZEN
Next module automatically scheduled
```

---

## 4. WRITE LOCK SYSTEM

### Lock Structure
```json
{
  "module": 2,
  "scope": "backend/apps/license/services/planning",
  "agent": "planning-implementation",
  "mode": "WRITE",
  "created_at": "2026-08-10T...",
  "expires_at": "2026-08-11T...",
  "heartbeat_at": "...",
  "status": "ACTIVE"
}
```

### Lock Rules
- One writer per scope
- Lock creation requires: module DISCOVERY gate PASS
- Lock timeout: 24 hours (extend on heartbeat)
- Conflict resolution: QUEUED agent waits for lock release
- Stale detection: Heartbeat missing → recovery protocol

---

## 5. DEPENDENCY GRAPH

Build from:
- Import analysis
- Model ForeignKeys
- Service dependencies
- API consumers
- Celery task dependencies

Structure:
```json
{
  "module_2": {
    "depends_on": ["module_1"],
    "blocks": ["module_3", "module_4"],
    "safe_parallel_with": ["module_5", "module_6", "module_7"],
    "estimated_duration_hours": 2.5
  },
  "module_3": {
    "depends_on": ["module_2"],
    ...
  }
}
```

---

## 6. AGENT REGISTRY

Track each agent:
```json
{
  "agent_id": "agent_123",
  "role": "PLANNING_IMPLEMENTATION",
  "module": 2,
  "phase": "IMPLEMENTATION",
  "mode": "WRITE",
  "status": "RUNNING",
  "started_at": "...",
  "last_heartbeat": "...",
  "files_locked": ["backend/apps/license/services/planning/"],
  "evidence_file": "audit_evidence/module_2/implementation.json",
  "result": null
}
```

---

## 7. EVIDENCE COLLECTION

After every agent:
```
audit_evidence/
  runtime/
    module_2/
      discovery.json
      implementation.json
      tests.json
      security.json
      parity.json
  gates/
    module_2_discovery.json
    module_2_business.json
    module_2_golden.json
    module_2_runtime.json
    module_2_adversarial.json
    module_2_freeze.json
```

Evidence format:
```json
{
  "phase": "DISCOVERY",
  "module": 2,
  "agent": "forensic_auditor",
  "timestamp": "...",
  "result": "PASS",
  "files_generated": ["MODULE_2_BASELINE.md", ...],
  "blockers": [],
  "evidence": {...}
}
```

---

## 8. CHECKPOINT SYSTEM

After every state transition:
```
docs/orchestrator/checkpoints/
  2026-08-10_1630_module1_freeze.json
  2026-08-10_1650_module2_discovery_start.json
  2026-08-10_1700_module2_discovery_complete.json
  2026-08-10_1800_module2_business_gate_pass.json
  ...
```

Checkpoint structure:
```json
{
  "timestamp": "2026-08-10T16:30:00Z",
  "program_state": "EXECUTING",
  "current_module": 1,
  "current_phase": "FREEZE",
  "modules": {...},
  "agents": {...},
  "locks": {...},
  "blockers": [],
  "git_head": "22eda417",
  "git_status": "clean",
  "next_action": "Launch Module 2 discovery"
}
```

---

## 9. GIT SAFETY

Protected files (never modify without approval):
```
.gitignore
CLAUDE.md
LICENSE
README.md
docs/CURRENT_PHASE.md
docs/AGENT_STATE.md
docs/MODULE_EXECUTION_MATRIX.md
docs/orchestrator/
docs/modules/MODULE_1_*
```

Before every write:
```
1. git status --short → verify clean or expected changes only
2. git diff --stat → verify scope matches write lock
3. Stage only locked scope files
4. Create logical commit
5. git diff --cached --check → verify no trailing whitespace
6. Commit with message referencing module and phase
```

---

## 10. AUTOMATIC CONTINUATION LOGIC

After every FREEZE:
```python
def next_module():
    frozen = set of frozen modules
    all_modules = set of all modules 2-11
    remaining = all_modules - frozen
    
    for module in dependency_order(remaining):
        if all_dependencies_frozen(module):
            return module
    
    if not remaining:
        return FINAL_SYSTEM_AUDIT
    
    # No module ready yet, wait for dependency
    return WAIT
```

---

## 11. FAILURE HANDLING

### Blocker Types
```
SEMANTIC_AMBIGUITY — Business rule unclear
CALCULATION_CONFLICT — Two authoritative sources disagree
DATA_LOSS_RISK — Migration could lose data
SECURITY_VULNERABILITY — Critical security issue
ENVIRONMENT_FAILURE — Tests cannot run (no recovery)
DESIGN_FAILURE — Canonical design conflict
```

### Retry Policy
```
Read-only agent failure: Retry up to 3 times
Test infrastructure failure: Retry with environment recovery
Write agent failure: Do NOT auto-retry; escalate to BLOCKED
```

### Recovery Actions
```
BLOCKED_ON_ENVIRONMENT:
  → Attempt to repair environment
  → If successful, retry agent
  → If not, escalate to BLOCKED

BLOCKED_ON_SEMANTIC:
  → Persist blocker with evidence
  → Continue other independent modules
  → Flag for human resolution

BLOCKED_ON_CONFLICT:
  → Run adversarial resolution
  → If unresolved, escalate to BLOCKED
```

---

## 12. PARALLEL EXECUTION STRATEGY

```
                    DISCOVERY POOL (10 agents)
                    ↓
         ┌──────────┼──────────┐
         ↓          ↓          ↓
       M2         M3         M4
    DESIGN      DISC       DISC
         ↓
    IMPLEMENT (1 agent, write lock)
         ↓
    VERIFICATION (5 agents, read-only)
         ↓
     FREEZE
```

---

## 13. FINAL RELEASE GATE

All modules FROZEN ✅  
Full system regression: PASS ✅  
Security audit: PASS ✅  
Performance audit: PASS ✅  
UI/UX audit: PASS ✅  
Data integrity: VERIFIED ✅  
Duplicate calculations: ZERO ✅  
Final documentation: COMPLETE ✅  

---

## 14. IMPLEMENTATION PRIORITY

1. **Core State System** — state.json, modules.json, agents.json
2. **Dependency Engine** — Build dependency graph from code
3. **Lock System** — Acquire/release, conflict detection
4. **Gate System** — Pass/fail/blocked logic
5. **Agent Registry** — Track agent state
6. **CLI Interface** — start, status, resume, dry-run
7. **Recovery System** — Checkpoint and resume
8. **Continuous Loop** — Auto-advance through modules

---

**Next:** Build the state files and CLI.
