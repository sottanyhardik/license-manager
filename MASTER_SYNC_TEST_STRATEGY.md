# Master Sync Test Strategy (MODULE 04 — PHASE 26)

## Executive Summary

This document defines a **parametrized test framework** for all 16 Master models to eliminate test file duplication while ensuring comprehensive coverage of sync behavior (CREATE, UPDATE, DELETE, conflict resolution, offline recovery).

**Key Principle**: One parametrized test suite tests all 16 Masters through shared behavior; model-specific tests only exist where behavior genuinely differs.

---

## 1. MASTER_MODELS_REGISTRY

### Registry: All 16 Masters with Natural Keys

| # | Model Name | Natural Key Field(s) | Composite? | Delete-Protected? | Synthetic UID? | Notes |
|---|---|---|---|---|---|---|
| 1 | `CompanyModel` | `iec` | No | Yes (transactional refs) | No | Standard audit model |
| 2 | `PortModel` | `code` | No | Yes (shipment refs) | No | Standard audit model |
| 3 | `ItemGroupModel` | `code` | No | No | No | Standard audit model |
| 4 | `ItemNameModel` | `code` | No | Yes (item refs) | No | Standard audit model |
| 5 | `HSCodeModel` | `code` | No | Yes (item refs) | No | Standard audit model |
| 6 | `HeadSIONNormsModel` | `name` | No | No | Yes | Synthetic UID (name-based) |
| 7 | `SionNormClassModel` | `code` | No | No | No | Standard audit model |
| 8 | `SIONExportModel` | `code` | No | Yes (export refs) | Yes | Composite: code + qty + unit |
| 9 | `SIONImportModel` | `serial_number` | No | Yes (import refs) | Yes | Composite: serial + desc + qty |
| 10 | `SionNormNote` | `(parent_id, display_order, note_text)` | **Yes** | No | Yes | Child table, 3-part key |
| 11 | `SionNormCondition` | `(parent_id, display_order, condition_text)` | **Yes** | No | Yes | Child table, 3-part key |
| 12 | `ProductDescriptionModel` | `product_description` | No | No | Yes | Synthetic UID (desc-based) |
| 13 | `UnitPriceModel` | `(name, unit_price, label)` | **Yes** | No | Yes | Composite: name + price + label |
| 14 | `SchemeCode` | `code` | No | No | No | No audit (minimal) |
| 15 | `NotificationNumber` | `number` | No | No | No | No audit (minimal) |
| 16 | `ExchangeRateModel` | `date` | No | No | No | Standard audit model |

---

## 2. Test Architecture: Parametrized Framework

### 2.1 Fixture Design Pattern

**Goal**: Single set of fixtures, parametrized over all 16 models, with model-specific overrides only when needed.

```python
# backend/apps/core/tests/test_master_sync_parametrized.py

import pytest
import uuid
from django.utils import timezone
from apps.core.models import (
    CompanyModel, PortModel, ItemGroupModel, ItemNameModel, HSCodeModel,
    HeadSIONNormsModel, SionNormClassModel, SIONExportModel, SIONImportModel,
    SionNormNote, SionNormCondition, ProductDescriptionModel, UnitPriceModel,
    SchemeCode, NotificationNumber, ExchangeRateModel
)

# Master model registry for parametrization
MASTER_MODELS = [
    CompanyModel, PortModel, ItemGroupModel, ItemNameModel, HSCodeModel,
    HeadSIONNormsModel, SionNormClassModel, SIONExportModel, SIONImportModel,
    SionNormNote, SionNormCondition, ProductDescriptionModel, UnitPriceModel,
    SchemeCode, NotificationNumber, ExchangeRateModel
]

# Model-specific factory functions (only overrides differ)
MASTER_FACTORIES = {
    'CompanyModel': lambda: {'iec': f'C{uuid.uuid4().int % 10000:04d}', 'name': 'Test Co'},
    'PortModel': lambda: {'code': f'P{uuid.uuid4().int % 1000:03d}', 'name': 'Test Port'},
    'ItemGroupModel': lambda: {'code': f'IG{uuid.uuid4().int % 100:02d}', 'name': 'Test Group'},
    'ItemNameModel': lambda: {'code': f'IN{uuid.uuid4().int % 100:02d}', 'name': 'Test Item'},
    'HSCodeModel': lambda: {'code': f'{uuid.uuid4().int % 100000000:08d}', 'description': 'HS'},
    'HeadSIONNormsModel': lambda: {'name': f'SION{uuid.uuid4().int % 10000:04d}'},
    'SionNormClassModel': lambda: {'code': f'SNC{uuid.uuid4().int % 100:02d}'},
    'SIONExportModel': lambda: {'code': f'EX{uuid.uuid4().int % 1000:03d}', 'quantity': 100, 'unit': 'KG'},
    'SIONImportModel': lambda: {'serial_number': uuid.uuid4().int % 10000, 'description': 'Import', 'quantity': 100, 'unit': 'KG'},
    'SionNormNote': lambda: {'parent_id': 1, 'display_order': 1, 'note_text': 'Test Note'},  # Requires parent
    'SionNormCondition': lambda: {'parent_id': 1, 'display_order': 1, 'condition_text': 'Test Condition'},  # Requires parent
    'ProductDescriptionModel': lambda: {'product_description': f'Prod{uuid.uuid4().int % 10000:04d}'},
    'UnitPriceModel': lambda: {'name': f'UP{uuid.uuid4().int % 100:02d}', 'unit_price': 100.00, 'label': 'INR'},
    'SchemeCode': lambda: {'code': f'SC{uuid.uuid4().int % 100:02d}'},
    'NotificationNumber': lambda: {'number': f'NN{uuid.uuid4().int % 10000:04d}'},
    'ExchangeRateModel': lambda: {'date': timezone.now().date(), 'usd': 84.50}
}

@pytest.fixture(params=MASTER_MODELS, ids=lambda m: m.__name__)
def master_model(request):
    """Parametrize all tests over the 16 Master models."""
    return request.param

@pytest.fixture
def factory_kwargs(master_model):
    """Get model-specific factory kwargs."""
    factory_fn = MASTER_FACTORIES.get(master_model.__name__)
    if factory_fn is None:
        pytest.skip(f"No factory for {master_model.__name__}")
    return factory_fn()
```

### 2.2 Parametrized Test Classes

Each test class tests all 16 models with the same assertions. Override only where behavior diverges.

---

## 3. Test Coverage Matrix

### 3.1 UID and Identity (Shared)

**File**: `test_master_sync_parametrized.py::TestMasterUIDDeterminism`

| Test | Purpose | All Models? | Skip? |
|---|---|---|---|
| `test_uid_computed_on_create` | UID assigned on first save | ✅ ALL | Only composite-key models |
| `test_uid_deterministic` | Same natural key = same UID | ✅ ALL | No |
| `test_uid_immutable_on_update` | UID never changes | ✅ ALL | No |
| `test_uid_unique_per_natural_key` | Different NK = different UID | ✅ ALL | No |
| `test_natural_key_field_present` | Model has identified natural key | ✅ ALL | No |
| `test_master_version_starts_at_1` | Version initialized to 1 | ✅ ALL | No |

**Rationale**: All 16 models inherit `MasterSyncMixin`, so UID behavior is identical.

---

### 3.2 CREATE Sync (Outbox/Inbox)

**File**: `test_master_sync_parametrized.py::TestCREATESyncFlow`

| Test | Purpose | All Models? | Notes |
|---|---|---|---|
| `test_create_generates_outbox_entry` | CREATE operation → outbox | ✅ ALL | Signal-driven |
| `test_outbox_has_valid_payload_hash` | Payload hash is SHA256 | ✅ ALL | Deterministic |
| `test_create_inbox_idempotency` | Duplicate inbox events dedupe | ✅ ALL | event_uuid is key |
| `test_create_payload_includes_natural_key` | Outbox payload has NK fields | ⚠️ Model-specific | Override per model |
| `test_create_version_is_1` | New record version = 1 | ✅ ALL | No |
| `test_create_deleted_false` | New record not soft-deleted | ✅ ALL | No |

---

### 3.3 UPDATE Sync (Version Increment)

**File**: `test_master_sync_parametrized.py::TestUPDATESyncFlow`

| Test | Purpose | All Models? | Notes |
|---|---|---|---|
| `test_update_increments_version` | Version ++ on UPDATE | ✅ ALL | Auto on save |
| `test_update_generates_outbox` | UPDATE operation → outbox | ✅ ALL | Signal-driven |
| `test_update_version_is_cumulative` | v1 → v2 → v3 → ... | ✅ ALL | No reset |
| `test_update_uid_unchanged` | UID stays same after update | ✅ ALL | Immutable |
| `test_update_timestamp_recorded` | modified_on updated | ⚠️ Audit models only | Skip non-audit |
| `test_update_payload_reflects_changes` | Outbox shows new values | ⚠️ Model-specific | Override per model |

---

### 3.4 DELETE Protection (Soft-Delete)

**File**: `test_master_sync_parametrized.py::TestDELETEProtection`

| Test | Purpose | All Models? | Notes |
|---|---|---|---|
| `test_delete_marks_soft_deleted` | DELETE → deleted=True | ✅ ALL | via mark_deleted() |
| `test_delete_sets_tombstone_version` | Tombstone tracks version at delete | ✅ ALL | No |
| `test_delete_sets_deleted_at` | deleted_at timestamp recorded | ✅ ALL | timezone.now() |
| `test_delete_generates_outbox` | DELETE operation → outbox | ✅ ALL | Signal-driven |
| `test_delete_in_use_rejected` | Transactional refs prevent delete | ⚠️ Protected only | Skip unprotected |
| `test_delete_in_use_error_message` | Error lists referencing models | ⚠️ Protected only | check_local_usage |
| `test_undelete_via_mark_active` | Recovery from soft-delete | ✅ ALL | No |
| `test_undelete_version_increments` | Recovery is new event (v++`) | ✅ ALL | No |

**Skip Matrix**: 
- `test_delete_in_use_*`: Only `CompanyModel`, `PortModel`, `ItemNameModel`, `HSCodeModel`, `SIONExportModel`, `SIONImportModel`

---

### 3.5 Conflict Resolution

**File**: `test_master_sync_parametrized.py::TestConflictResolution`

| Test | Purpose | All Models? | Notes |
|---|---|---|---|
| `test_concurrent_updates_same_uid` | Two servers update same UID | ✅ ALL | Version check |
| `test_conflict_recorded_as_masterconflict` | Conflict logged for manual review | ✅ ALL | event_uid is key |
| `test_version_check_prevents_stale_apply` | v1 inbox rejected if v2 exists | ✅ ALL | Version comparison |
| `test_higher_version_wins` | Latest version takes precedence | ✅ ALL | LIFO semantics |
| `test_concurrent_deletes_idempotent` | DELETE DELETE = DELETE | ✅ ALL | Tombstone tracking |
| `test_create_after_delete_recovery` | CREATE inbox received after DELETE | ✅ ALL | Resurrection scenario |
| `test_hash_mismatch_detected` | Payload corruption detected | ✅ ALL | payload_hash check |

---

### 3.6 Offline Recovery

**File**: `test_master_sync_parametrized.py::TestOfflineRecovery`

| Test | Purpose | All Models? | Notes |
|---|---|---|---|
| `test_outbox_queues_during_offline` | Outbox fills during network loss | ✅ ALL | persistence |
| `test_cursor_tracks_last_applied` | Sync cursor saves progress | ✅ ALL | resume from cursor |
| `test_resume_from_cursor` | Sync resumes from last applied | ✅ ALL | No re-process |
| `test_inbox_duplicate_dedupe` | Inbox dedupes on event_uuid | ✅ ALL | Idempotent replay |
| `test_missing_parent_queues_for_retry` | Child refs missing parent → retry | ⚠️ Composite keys only | SionNormNote, etc. |
| `test_retry_queue_backoff` | Exponential backoff on retries | ✅ ALL | master_sync_retry |
| `test_reconciliation_detects_drift` | Offline changes detected on resync | ✅ ALL | find_duplicates_by_natural_key |

**Skip Matrix**:
- `test_missing_parent_queues_for_retry`: Only `SionNormNote`, `SionNormCondition`, `UnitPriceModel`

---

## 4. Implementation Plan: Parametrized Tests

### 4.1 File Structure

```
backend/apps/core/tests/
├── __init__.py
├── conftest.py                                  # Shared fixtures
├── test_master_sync_parametrized.py             # ← NEW: All 16 models
│   ├── TestMasterUIDDeterminism
│   ├── TestCREATESyncFlow
│   ├── TestUPDATESyncFlow
│   ├── TestDELETEProtection
│   ├── TestConflictResolution
│   └── TestOfflineRecovery
├── test_master_sync_model_specific.py           # ← Model-specific overrides (minimal)
│   ├── TestCompanyModelSpecific
│   ├── TestSionNormNoteSpecific                 # Composite key special case
│   └── ...
├── test_master_sync_unit.py                     # ← Keep (outbox/inbox/cursor/media)
└── test_master_sync_integration.py              # ← Keep (full end-to-end)
```

### 4.2 Parametrization Example: CREATE Sync

```python
# backend/apps/core/tests/test_master_sync_parametrized.py

class TestCREATESyncFlow:
    """Test CREATE behavior across all 16 Master models."""

    def test_create_generates_outbox_entry(self, master_model, factory_kwargs, db):
        """Creating a Master generates outbox entry."""
        obj = master_model.objects.create(**factory_kwargs)
        
        outbox = MasterSyncOutbox.objects.filter(
            master_uid=obj.master_uid,
            operation='CREATE'
        )
        assert outbox.exists(), f"{master_model.__name__} CREATE not logged"

    def test_create_version_is_1(self, master_model, factory_kwargs, db):
        """New record has version=1."""
        obj = master_model.objects.create(**factory_kwargs)
        assert obj.master_version == 1, f"{master_model.__name__} version != 1"

    def test_create_deleted_false(self, master_model, factory_kwargs, db):
        """New record not soft-deleted."""
        obj = master_model.objects.create(**factory_kwargs)
        assert obj.deleted is False, f"{master_model.__name__} deleted != False"

    @pytest.mark.parametrize("operation", ['CREATE'])
    def test_outbox_operation_recorded(self, master_model, factory_kwargs, db, operation):
        """Outbox records correct operation."""
        obj = master_model.objects.create(**factory_kwargs)
        outbox = MasterSyncOutbox.objects.get(master_uid=obj.master_uid)
        assert outbox.operation == operation
```

### 4.3 Model-Specific Overrides (Minimal)

Only override when behavior genuinely differs. Example: Composite-key models.

```python
# backend/apps/core/tests/test_master_sync_model_specific.py

class TestSionNormNoteSpecific:
    """Test SionNormNote (composite key: parent_id, display_order, note_text)."""

    def test_sion_norm_note_requires_parent(self, db):
        """SionNormNote cannot exist without parent."""
        with pytest.raises(ValueError):
            SionNormNote.objects.create(
                display_order=1,
                note_text="Orphan Note"
                # Missing parent_id
            )

    def test_sion_norm_note_composite_key_unique(self, db):
        """(parent_id, display_order, note_text) is unique."""
        parent = HeadSIONNormsModel.objects.create(name='Parent')
        
        # First note
        note1 = SionNormNote.objects.create(
            parent_id=parent.id,
            display_order=1,
            note_text="Same Note"
        )
        
        # Duplicate should fail
        with pytest.raises(IntegrityError):
            SionNormNote.objects.create(
                parent_id=parent.id,
                display_order=1,
                note_text="Same Note"  # Same composite key
            )
```

---

## 5. Delete Protection Registry

**Models protecting delete** (transactional references exist):
- `CompanyModel` → referenced in LicenseDetailsModel, BillOfEntryModel, LicenseTrade, AllotmentModel
- `PortModel` → referenced in LicenseDetailsModel, BillOfEntryModel, AllotmentModel
- `ItemNameModel` → referenced in LicenseImportItemsModel, BOE RowDetails
- `HSCodeModel` → referenced in transactional items
- `SIONExportModel` → referenced in export rules
- `SIONImportModel` → referenced in import rules

**Models allowing delete** (no transactional references):
- `ItemGroupModel`, `SionNormClassModel`, `SchemeCode`, `NotificationNumber`, `ExchangeRateModel`, `HeadSIONNormsModel`, `SionNormNote`, `SionNormCondition`, `ProductDescriptionModel`, `UnitPriceModel`

---

## 6. Test Execution Strategy

### 6.1 Run Parametrized Tests

```bash
# Run all 16 models through common behavior
pytest backend/apps/core/tests/test_master_sync_parametrized.py -v

# Run only CompanyModel
pytest backend/apps/core/tests/test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[CompanyModel] -v

# Run only UPDATE tests for all models
pytest backend/apps/core/tests/test_master_sync_parametrized.py::TestUPDATESyncFlow -v
```

### 6.2 Run Model-Specific Tests

```bash
# Run override tests for composite-key models
pytest backend/apps/core/tests/test_master_sync_model_specific.py -v
```

### 6.3 Full Suite

```bash
# Run complete test suite
pytest backend/apps/core/tests/ -k "master_sync" -v --tb=short

# Run with coverage
pytest backend/apps/core/tests/ -k "master_sync" --cov=apps.core --cov-report=html
```

---

## 7. Test Data Factories

### 7.1 `conftest.py` Fixtures

```python
# backend/apps/core/tests/conftest.py

import pytest
import uuid
from django.utils import timezone

@pytest.fixture
def master_sync_server(db):
    """Create a test sync server."""
    from apps.core.models import MasterSyncServer
    return MasterSyncServer.objects.create(
        server_id='TEST_SERVER_001',
        api_url='http://test-server.local/api'
    )

@pytest.fixture
def master_company(db):
    """Create a test CompanyModel."""
    from apps.core.models import CompanyModel
    return CompanyModel.objects.create(
        iec=f'C{uuid.uuid4().int % 10000:04d}',
        name='Test Exporter'
    )

@pytest.fixture
def master_port(db):
    """Create a test PortModel."""
    from apps.core.models import PortModel
    return PortModel.objects.create(
        code=f'P{uuid.uuid4().int % 1000:03d}',
        name='Test Port'
    )

# ... more fixtures per model as needed
```

---

## 8. Coverage Goals

| Category | Target | Achieved By |
|---|---|---|
| All 16 Models (Shared) | 100% | Parametrized tests |
| CREATE Sync | 100% | TestCREATESyncFlow (10 tests × 16 models = 160 assertions) |
| UPDATE Sync | 100% | TestUPDATESyncFlow (7 tests × 16 models = 112 assertions) |
| DELETE Protection | 100% | TestDELETEProtection (8 tests, skips on non-protected) |
| Conflict Resolution | 100% | TestConflictResolution (7 tests × 16 models = 112 assertions) |
| Offline Recovery | 100% | TestOfflineRecovery (7 tests, skips on non-composite) |
| Model-Specific Behavior | 100% | test_master_sync_model_specific.py (overrides only) |

**Total assertions**: ~500-600 (covering all 16 models with parametrization)

---

## 9. Benefits of Parametrized Approach

| Benefit | Rationale |
|---|---|
| **No duplication** | One test suite, all 16 models. Adding model 17 = one registry entry. |
| **Maintainability** | Bug fix in shared behavior = fixed in one place. |
| **Scalability** | New Masters (e.g., `ShippingMarkModel`) just register in `MASTER_MODELS`. |
| **Clear overrides** | Model-specific tests sit separately, easy to spot exceptions. |
| **CI/CD clarity** | Parametrized output shows: `test_create_generates_outbox[CompanyModel]`, `test_create_generates_outbox[PortModel]`, etc. |
| **Regression prevention** | If a test passes for 15 models but fails for model 16, you catch it immediately. |

---

## 10. Implementation Roadmap

| Phase | Deliverable | Owner | Duration |
|---|---|---|---|
| 1 | Parametrized base (`test_master_sync_parametrized.py`) | Test Architect | 2h |
| 2 | Model-specific overrides (`test_master_sync_model_specific.py`) | Test Architect | 1h |
| 3 | Factories & fixtures in `conftest.py` | QA | 1h |
| 4 | Run & validate all tests | QA | 1h |
| 5 | Coverage report + CI/CD integration | DevOps | 1h |

**Total**: ~6 hours to full parametrized test suite for all 16 Masters.

---

## 11. Example Output: Test Run

```bash
$ pytest backend/apps/core/tests/test_master_sync_parametrized.py::TestCREATESyncFlow -v

test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[CompanyModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[PortModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[ItemGroupModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[ItemNameModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[HSCodeModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[HeadSIONNormsModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[SionNormClassModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[SIONExportModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[SIONImportModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[SionNormNote] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[SionNormCondition] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[ProductDescriptionModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[UnitPriceModel] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[SchemeCode] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[NotificationNumber] PASSED
test_master_sync_parametrized.py::TestCREATESyncFlow::test_create_generates_outbox_entry[ExchangeRateModel] PASSED

========================== 16 passed in 0.42s ==========================
```

---

## 12. Next Steps

1. **Implement** `test_master_sync_parametrized.py` with all 6 test classes (UID, CREATE, UPDATE, DELETE, Conflict, Recovery)
2. **Implement** `test_master_sync_model_specific.py` with overrides for composite-key & protected models
3. **Validate** all factories in `conftest.py`
4. **Run** complete parametrized test suite: `pytest backend/apps/core/tests/ -k "master_sync" --tb=short`
5. **Integrate** into CI/CD pipeline
6. **Document** in project README as the canonical Master sync test approach

---

## Appendix A: Master Model Metadata

```python
MASTER_MODEL_METADATA = {
    'CompanyModel': {
        'natural_key': 'iec',
        'delete_protected': True,
        'synthetic_uid': False,
        'composite_key': False,
        'audit_fields': True,
    },
    'SionNormNote': {
        'natural_key': ('parent_id', 'display_order', 'note_text'),
        'delete_protected': False,
        'synthetic_uid': True,
        'composite_key': True,
        'audit_fields': True,
    },
    # ... 14 more entries
}
```

---

**Version**: 1.0  
**Status**: PHASE 26 — Ready for Implementation  
**Author**: Test Architect (Agent 7)  
**Date**: 2026-08-12
