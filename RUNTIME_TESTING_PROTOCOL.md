# MODULE 04 RUNTIME TESTING PROTOCOL

**CEO Directive**: Runtime behavior must be proven with actual execution. No agent may declare success based only on source-code inspection.

## Phase 8: Parametrized Test Framework

**Objective**: Replace duplicated test files with parametrized tests.

### Architecture

```python
MASTER_MODELS_REGISTRY = [
    {'model': CompanyModel, 'natural_key': ['iec_code']},
    {'model': PortModel, 'natural_key': ['port_code']},
    {'model': ItemGroupModel, 'natural_key': ['item_group_code']},
    # ... 13 more
]

@pytest.mark.parametrize('master_model', MASTER_MODELS_REGISTRY)
def test_create_sync(master_model):
    # Tests all 16 Masters with same logic
    pass

@pytest.mark.parametrize('master_model', MASTER_MODELS_REGISTRY)
def test_update_sync(master_model):
    pass

@pytest.mark.parametrize('master_model', MASTER_MODELS_REGISTRY)
def test_delete_protection(master_model):
    pass

@pytest.mark.parametrize('master_model', MASTER_MODELS_REGISTRY)
def test_conflict_resolution(master_model):
    pass

@pytest.mark.parametrize('master_model', MASTER_MODELS_REGISTRY)
def test_offline_recovery(master_model):
    pass
```

### Test Assertions

- `assert_master_converged()` — Verify A == B == C
- `assert_no_duplicate_master()` — No duplicate UIDentifiers
- `assert_media_hash_equal()` — SHA256 matches
- `assert_delete_protected()` — Usage checking works
- `assert_event_idempotent()` — Reapplying event is safe

## Phases 9-24: Runtime Testing

### Phase 9: Conflict Test
```
Create same Master on A and B with different values.
Perform concurrent updates on both.
Verify deterministic conflict resolution.
Expected: Same final state across A/B/C.
```

### Phase 10: Offline Test
```
Stop SERVER_C.
Modify Master on A.
Modify Master on B.
Restart C.
Expected: C automatically catches up to A==B==C.
```

### Phase 11: Failure Test
Simulate:
- Network timeout
- Duplicate event
- Malformed event
- Out-of-order event
- Server restart
- Celery restart
- Media transfer failure
- Database transaction rollback

Expected: No data loss, eventual convergence.

### Phase 12: Full Matrix Test
Test all 16 Masters through parametrized tests.
- CREATE sync (3 directions)
- UPDATE sync (3 directions)
- DELETE protection
- Conflict resolution
- Media sync

### Phases 13-24: Extended Testing
- Stress testing (high volume)
- Long-duration stability
- Network partition recovery
- Cascading failures
- Rollback scenarios

## Phase 25: Freeze Gate Validation

Run FREEZE_GATE_CHECKLIST.md:
- [ ] All 47 gates checked
- [ ] Evidence collected for each gate
- [ ] All gates: PASS

## Phase 26: Final Freeze Report

Produce: `MODULE_04_MASTER_SYNC_FINAL_AUDIT.md`

Include:
1. Architecture overview
2. Master inventory (16 models)
3. Sync architecture (Outbox/Inbox/Conflict)
4. Common-code architecture
5. UID strategy (UUID5 determinism)
6. Version strategy (increment on UPDATE)
7. Tombstone strategy
8. Media synchronization
9. Conflict handling (version + server-ID tiebreaker)
10. Duplicate reconciliation (natural-key uniqueness)
11. Delete protection (usage checking)
12. Retry/recovery (event replay)
13. Security (auth, authz, secrets)
14. Backend audit findings
15. Frontend audit findings
16. UI/UX audit findings
17. Code duplication before/after
18. Library reuse summary
19. Performance analysis
20. Test coverage matrix
21. A/B/C convergence evidence
22. Production safety verification
23. Git history
24. Risk assessment
25. Recommendation: FROZEN or BLOCKED

---

**Prepared**: 2026-08-12  
**Status**: READY_FOR_EXECUTION
