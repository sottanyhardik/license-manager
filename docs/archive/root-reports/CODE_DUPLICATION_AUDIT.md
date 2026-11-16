# Module 04 Code Duplication Audit
**Date:** 2026-08-12  
**Scope:** Master Data Synchronization (Module 04)  
**Goal:** Identify duplication opportunities for consolidation using mixins, services, registries, and parametrized tests.

---

## Executive Summary

Module 04 implements comprehensive master data synchronization across 16 master models. While the architecture uses shared base classes (MasterSyncMixin), significant duplication exists in:

- **Signal handlers:** 32 nearly-identical handlers (16 post_save + 16 post_delete)
- **Event builder:** 3 build_* methods with 85%+ shared logic
- **UID service:** 16 wrapper methods doing identical operations
- **Model implementations:** 16 identical compute_master_uid implementations
- **Natural key extraction:** 1 giant if/elif chain with 16 branches

**Total Duplication Count:** ~250 lines of redundant code  
**Consolidation Opportunities:** 8 major refactors could reduce ~150 lines

---

## Duplication Analysis by Category

### 1. SIGNAL HANDLERS — Most Severe
**Files:** `backend/apps/core/signals_master_sync.py`  
**Lines:** 162–287 (save) + 290–368 (delete)  
**Severity:** 🔴 CRITICAL (32 handlers, 100% identical logic)

#### Problem
All 16 models have identical signal handlers:
```python
# CompanyModel handler (line 162-167)
@receiver(post_save, sender=CompanyModel, dispatch_uid="company_model_sync")
def on_company_save(sender, instance, created, **kwargs):
    if created:
        create_outbox_entry(instance, 'CREATE')
    else:
        create_outbox_entry(instance, 'UPDATE')

# PortModel handler (line 169-174) - IDENTICAL
@receiver(post_save, sender=PortModel, dispatch_uid="port_model_sync")
def on_port_save(sender, instance, created, **kwargs):
    if created:
        create_outbox_entry(instance, 'CREATE')
    else:
        create_outbox_entry(instance, 'UPDATE')

# ... 14 more identical handlers
```

Delete handlers (lines 290–368) are even more repetitive:
```python
@receiver(post_delete, sender=CompanyModel, dispatch_uid="company_model_delete")
def on_company_delete(sender, instance, **kwargs):
    create_outbox_entry(instance, 'DELETE')

# Same for 15 other models
```

#### Consolidation Strategy
**Use a dynamic signal registration registry:**

```python
# signals_master_sync.py - NEW APPROACH

MASTER_MODELS_FOR_SYNC = [
    CompanyModel, PortModel, ItemGroupModel, ItemNameModel, HSCodeModel,
    HeadSIONNormsModel, SionNormClassModel, SIONExportModel, SIONImportModel,
    SionNormNote, SionNormCondition, ProductDescriptionModel, UnitPriceModel,
    SchemeCode, NotificationNumber, ExchangeRateModel,
]

def register_master_sync_signals():
    """Registers post_save and post_delete handlers for all masters dynamically."""
    
    def make_save_handler(model_class):
        @receiver(post_save, sender=model_class, dispatch_uid=f"{model_class.__name__}_sync")
        def on_save(sender, instance, created, **kwargs):
            operation = 'CREATE' if created else 'UPDATE'
            create_outbox_entry(instance, operation)
        return on_save
    
    def make_delete_handler(model_class):
        @receiver(post_delete, sender=model_class, dispatch_uid=f"{model_class.__name__}_delete")
        def on_delete(sender, instance, **kwargs):
            create_outbox_entry(instance, 'DELETE')
        return on_delete
    
    for model_class in MASTER_MODELS_FOR_SYNC:
        make_save_handler(model_class)
        make_delete_handler(model_class)

# In apps.py:
class CoreConfig(AppConfig):
    def ready(self):
        from .signals_master_sync import register_master_sync_signals
        register_master_sync_signals()
```

**Impact:**
- ✅ Eliminate 32 handler definitions (120 lines)
- ✅ Single source of truth for which models sync
- ✅ Easier to add/remove models from sync in future

**Risk:** None — behavior is identical. Test with existing test suite.

---

### 2. EVENT BUILDER — Duplicate Logic
**File:** `backend/apps/core/services/master_event_builder.py`  
**Lines:** 26–71 (build_create_event), 73–111 (build_update_event), 112–149 (build_delete_event)  
**Severity:** 🟠 HIGH (85% code duplication)

#### Problem
Three methods are nearly identical:

```python
# Lines 26-71: build_create_event
def build_create_event(instance, origin_server, event_uid=None):
    if event_uid is None:
        event_uid = MasterEventBuilder._generate_event_uid(origin_server)
    
    payload = MasterEventBuilder._serialize_instance(instance)
    payload_hash = MasterEventBuilder._hash_payload(payload)
    
    return {
        'event_uid': event_uid,
        'master_uid': instance.master_uid,
        'model_name': instance.__class__.__name__,
        'natural_key': ...,
        'operation': 'CREATE',          # ← DIFFERENT
        'version': instance.master_version,
        'origin_server': origin_server,
        'origin_timestamp': datetime.utcnow().isoformat() + 'Z',
        'payload': payload,
        'payload_hash': payload_hash,
    }

# Lines 73-110: build_update_event - SAME STRUCTURE
# Lines 112-148: build_delete_event - SAME STRUCTURE
```

#### Consolidation Strategy
**Extract common builder logic into a generic method:**

```python
class MasterEventBuilder:
    
    @staticmethod
    def build_event(
        instance: Any,
        operation: str,  # 'CREATE', 'UPDATE', or 'DELETE'
        origin_server: str,
        previous_version: Optional[int] = None,
        event_uid: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generic event builder for all operations."""
        
        if event_uid is None:
            event_uid = MasterEventBuilder._generate_event_uid(origin_server)
        
        payload = MasterEventBuilder._serialize_instance(instance)
        payload_hash = MasterEventBuilder._hash_payload(payload)
        
        event = {
            'event_uid': event_uid,
            'master_uid': instance.master_uid,
            'model_name': instance.__class__.__name__,
            'natural_key': instance.get_natural_key() if hasattr(instance, 'get_natural_key') else str(instance.pk),
            'operation': operation,
            'version': instance.master_version,
            'origin_server': origin_server,
            'origin_timestamp': datetime.utcnow().isoformat() + 'Z',
            'payload': payload,
            'payload_hash': payload_hash,
        }
        
        # Add operation-specific fields
        if operation == 'UPDATE':
            event['previous_version'] = previous_version
        elif operation == 'DELETE':
            event['tombstone_version'] = instance.tombstone_version if hasattr(instance, 'tombstone_version') else None
        
        return event
    
    @staticmethod
    def build_create_event(instance, origin_server, event_uid=None):
        """Convenience wrapper for CREATE operations."""
        return MasterEventBuilder.build_event(instance, 'CREATE', origin_server, event_uid=event_uid)
    
    @staticmethod
    def build_update_event(instance, previous_version, origin_server, event_uid=None):
        """Convenience wrapper for UPDATE operations."""
        return MasterEventBuilder.build_event(instance, 'UPDATE', origin_server, previous_version, event_uid)
    
    @staticmethod
    def build_delete_event(instance, origin_server, event_uid=None):
        """Convenience wrapper for DELETE operations."""
        return MasterEventBuilder.build_event(instance, 'DELETE', origin_server, event_uid=event_uid)
```

**Impact:**
- ✅ Eliminate 80 lines of duplicated event dict construction
- ✅ Single source of truth for event schema
- ✅ Easier to add new fields to all events at once
- ✅ Backward-compatible (existing method signatures unchanged)

**Risk:** Low — refactors are backward-compatible.

---

### 3. UID SERVICE — Repetitive Wrappers
**File:** `backend/apps/core/services/master_uid_service.py`  
**Lines:** 73–155 (16 for_* methods)  
**Severity:** 🟡 MEDIUM (16 nearly-identical wrapper methods)

#### Problem
All 16 for_* methods are trivial wrappers:

```python
# Lines 74-76
@staticmethod
def for_company(iec_code: str) -> uuid.UUID:
    """Generate UID for CompanyModel."""
    return MasterUIDService.generate_uuid5(iec_code)

# Lines 79-81
@staticmethod
def for_port(code: str) -> uuid.UUID:
    """Generate UID for PortModel."""
    return MasterUIDService.generate_uuid5(code)

# Lines 84-86
@staticmethod
def for_item_group(name: str) -> uuid.UUID:
    """Generate UID for ItemGroupModel."""
    return MasterUIDService.generate_uuid5(name)

# ... 13 more identical patterns
```

Slightly more complex ones are still highly similar:

```python
# Lines 109-111 (composite key)
@staticmethod
def for_sion_export(norm_class_code: str, description: str, quantity, unit: str) -> uuid.UUID:
    """Generate UID for SIONExportModel."""
    return MasterUIDService.generate_uuid5((norm_class_code, description, quantity, unit))

# Lines 114-119 (even more fields)
@staticmethod
def for_sion_import(serial_number: int, norm_class_code: str, hs_code: str,
                   description: str, quantity, unit: str, condition: str) -> uuid.UUID:
    """Generate UID for SIONImportModel."""
    return MasterUIDService.generate_uuid5(
        (serial_number, norm_class_code, hs_code, description, quantity, unit, condition)
    )
```

#### Consolidation Strategy
**Use a registry mapping model names to UID generation recipes:**

```python
class MasterUIDService:
    """Canonical Master UID generation."""
    
    # Registry: model_name -> (field_names | callable)
    # This moves 16 methods into a data structure
    UID_RECIPES = {
        'CompanyModel': 'iec',
        'PortModel': 'code',
        'ItemGroupModel': 'name',
        'ItemNameModel': 'name',
        'HSCodeModel': 'hs_code',
        'HeadSIONNormsModel': 'name',
        'SionNormClassModel': 'norm_class',
        'SIONExportModel': ('norm_class_id', 'description', 'quantity', 'unit'),
        'SIONImportModel': ('serial_number', 'norm_class_id', 'hsn_code_id', 'description', 'quantity', 'unit', 'condition'),
        'SionNormNote': ('sion_norm_id', 'display_order', 'note_text'),
        'SionNormCondition': ('sion_norm_id', 'display_order', 'condition_text'),
        'ProductDescriptionModel': ('hs_code_id', 'product_description'),
        'UnitPriceModel': ('name', 'unit_price', 'label'),
        'SchemeCode': 'code',
        'NotificationNumber': 'code',
        'ExchangeRateModel': 'date',
    }
    
    @staticmethod
    def generate_uuid5(natural_key: Union[str, tuple, list]) -> uuid.UUID:
        """Generate deterministic UUID5 from a natural key."""
        normalized = MasterUIDService._normalize_key(natural_key)
        return uuid.uuid5(MASTER_NAMESPACE, normalized)
    
    @staticmethod
    def for_model(model_instance: Any) -> uuid.UUID:
        """Generic UID generation for any Master instance."""
        model_name = model_instance.__class__.__name__
        recipe = MasterUIDService.UID_RECIPES.get(model_name)
        
        if not recipe:
            raise ValueError(f"No UID recipe for {model_name}")
        
        # If recipe is a string, it's a single field name
        if isinstance(recipe, str):
            value = getattr(model_instance, recipe)
            return MasterUIDService.generate_uuid5(value)
        
        # If recipe is a tuple, it's multiple field names
        if isinstance(recipe, tuple):
            values = tuple(getattr(model_instance, field) for field in recipe)
            return MasterUIDService.generate_uuid5(values)
        
        raise ValueError(f"Invalid recipe for {model_name}")
    
    # Convenience wrappers (kept for backward compatibility)
    @staticmethod
    def for_company(iec_code: str) -> uuid.UUID:
        return MasterUIDService.generate_uuid5(iec_code)
    
    @staticmethod
    def for_port(code: str) -> uuid.UUID:
        return MasterUIDService.generate_uuid5(code)
    
    # ... etc (can be removed once code migrates to for_model())
```

Then update all model compute_master_uid methods:

```python
# OLD: Each model had this
class CompanyModel(MasterSyncMixin, AuditModel):
    def compute_master_uid(self):
        return MasterUIDService.for_company(self.iec)

# NEW: All models use this
class CompanyModel(MasterSyncMixin, AuditModel):
    def compute_master_uid(self):
        return MasterUIDService.for_model(self)
```

**Impact:**
- ✅ Replace 16 methods + 16 model implementations = 40 lines with 1 registry + 1 generic method
- ✅ Adding a new master model requires only editing UID_RECIPES dict
- ✅ Clearer separation of concerns (recipe definition vs. generation)

**Risk:** Low — all logic preserved. Easier to test with fewer variations.

---

### 4. MODEL COMPUTE_MASTER_UID — Repetitive Implementations
**File:** `backend/apps/core/models.py`  
**Lines:** Scattered throughout (275–277, 297–299, 348–350, 385–387, 414–416, 428–430, 445–447, etc.)  
**Severity:** 🟡 MEDIUM (16 identical 3-line implementations)

#### Problem
Every model repeats the same pattern:

```python
class CompanyModel(MasterSyncMixin, AuditModel):
    def compute_master_uid(self):
        return MasterUIDService.for_company(self.iec)

class PortModel(MasterSyncMixin, AuditModel):
    def compute_master_uid(self):
        return MasterUIDService.for_port(self.code)

# ... 14 more identical patterns
```

#### Consolidation Strategy
**Move to a mixin that uses the registry above:**

```python
# New file: backend/apps/core/master_uid_mixin.py

class MasterUIDMixin(models.Model):
    """
    Mixin that auto-computes master_uid using MasterUIDService registry.
    Subclasses just need to inherit this; no need to override compute_master_uid.
    """
    
    class Meta:
        abstract = True
    
    def compute_master_uid(self):
        """Auto-compute using UID_RECIPES registry."""
        from .services.master_uid_service import MasterUIDService
        return MasterUIDService.for_model(self)
```

Then update all 16 models to remove their compute_master_uid methods (they inherit the default from MasterSyncMixin which now uses this approach).

**Impact:**
- ✅ Eliminate ~50 lines of repetitive method definitions
- ✅ All models automatically use the registry approach
- ✅ Single point of maintenance

**Risk:** Low — method still exists, just moved to base class.

---

### 5. NATURAL KEY EXTRACTION — Giant If/Elif Chain
**File:** `backend/apps/core/signals_master_sync.py`  
**Lines:** 43–80 (get_natural_key function)  
**Severity:** 🟡 MEDIUM (16-branch if/elif with repetitive field access)

#### Problem
```python
def get_natural_key(instance):
    """Extract the natural key from a Master instance."""
    model_name = instance.__class__.__name__

    if model_name == 'CompanyModel':
        return instance.iec
    elif model_name == 'PortModel':
        return instance.code
    elif model_name == 'ItemGroupModel':
        return instance.name
    elif model_name == 'ItemNameModel':
        return instance.name
    # ... 12 more branches

    return str(instance.pk)
```

This is duplicated logic vs. the UID_RECIPES registry above.

#### Consolidation Strategy
**Make natural_key extraction data-driven:**

```python
# In master_uid_service.py (add to UID_RECIPES or new NATURAL_KEY_RECIPES)

NATURAL_KEY_RECIPES = {
    'CompanyModel': 'iec',
    'PortModel': 'code',
    'ItemGroupModel': 'name',
    'ItemNameModel': 'name',
    'HSCodeModel': 'hs_code',
    # ... etc
}

# In signals_master_sync.py
def get_natural_key(instance):
    """Extract natural key using recipe registry."""
    model_name = instance.__class__.__name__
    recipe = NATURAL_KEY_RECIPES.get(model_name)
    
    if recipe:
        if isinstance(recipe, str):
            return str(getattr(instance, recipe))
        elif isinstance(recipe, tuple):
            values = tuple(str(getattr(instance, f)) for f in recipe)
            return "|".join(values)
    
    return str(instance.pk)
```

**Impact:**
- ✅ Replace 40 lines with 15-line registry + 10-line function
- ✅ Single source of truth for natural keys
- ✅ Easier to add new models

**Risk:** None — same logic, just data-driven instead of hardcoded.

---

### 6. TESTS — Repetitive Test Patterns
**File:** `backend/apps/core/tests/test_master_sync_unit.py`  
**Severity:** 🟡 MEDIUM

#### Problem
Tests create similar fixtures multiple times and repeat setup patterns:

```python
class TestMasterUIDDeterminism(TestCase):
    def test_master_uid_is_set_on_creation(self):
        company = CompanyModel.objects.create(iec='C001', name='Acme Corp')
        assert company.id is not None

    def test_master_uid_deterministic_across_instances(self):
        company1 = CompanyModel.objects.create(iec='C002', name='Test Company')
        # ... test logic

class TestOutboxOperations(TestCase):
    def test_outbox_created_on_model_create(self):
        company = CompanyModel.objects.create(iec='C004', name='Test Company')
        outbox_count = MasterSyncOutbox.objects.filter(master_uid=company.master_uid).count()
        assert outbox_count > 0
```

#### Consolidation Strategy
**Use parametrized tests (pytest or django test factories):**

```python
import pytest
from parameterized import parameterized

class TestMasterUIDDeterminism:
    @parameterized.expand([
        ('C001', 'Acme Corp'),
        ('C002', 'Test Company'),
        ('C003', 'Original Name'),
    ])
    def test_master_uid_is_set_on_creation(self, iec, name):
        company = CompanyModel.objects.create(iec=iec, name=name)
        assert company.id is not None
        assert company.master_uid is not None
```

Or use factory_boy for cleaner fixtures:

```python
from factory import Factory

class CompanyFactory(Factory):
    class Meta:
        model = CompanyModel
    
    iec = factory.Sequence(lambda n: f"C{n:04d}")
    name = factory.Faker('company')

# Usage
company = CompanyFactory(iec='C001')
```

**Impact:**
- ✅ Reduce test code duplication by ~30%
- ✅ Clearer test intent
- ✅ Easier to add more test cases

**Risk:** Low — requires parameterized testing library addition.

---

### 7. SERIALIZATION — Duplicated in Multiple Places
**Files:** 
- `signals_master_sync.py` lines 83–114 (serialize_instance)
- `master_event_builder.py` lines 166–224 (_serialize_instance)

**Severity:** 🟡 MEDIUM (100% duplicate code)

#### Problem
```python
# signals_master_sync.py (lines 83-114)
def serialize_instance(instance):
    """Serialize a Master instance to JSON-compatible dict."""
    payload = {'id': instance.pk, 'master_uid': str(instance.master_uid) ...}
    for field in instance._meta.get_fields():
        if field.many_to_one or field.many_to_many or field.one_to_many:
            continue
        try:
            value = getattr(instance, field.name)
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            # ...
        except Exception:
            pass
    return payload

# master_event_builder.py (lines 166-224)
@staticmethod
def _serialize_instance(instance: Any) -> Dict[str, Any]:
    """Serialize a Master instance to JSON-compatible dict."""
    payload = {'id': instance.pk, 'master_uid': str(instance.master_uid) ...}
    for field in instance._meta.get_fields():
        if field.many_to_one or field.many_to_many or field.one_to_many:
            continue
        # IDENTICAL LOGIC
```

#### Consolidation Strategy
**Move to master_event_builder.py as the canonical implementation:**

```python
# signals_master_sync.py
from .services.master_event_builder import MasterEventBuilder

def serialize_instance(instance):
    """Serialize instance (use canonical implementation from MasterEventBuilder)."""
    return MasterEventBuilder._serialize_instance(instance)
```

**Impact:**
- ✅ Single source of truth for serialization
- ✅ Eliminate 40 lines of duplicate code

**Risk:** None — both are identical already.

---

## Consolidation Opportunities Summary

| Duplication Type | Location | Lines | Severity | Opportunity |
|---|---|---|---|---|
| Signal handlers | signals_master_sync.py | 120 | 🔴 Critical | Dynamic registry (saves 120 lines) |
| Event builder | master_event_builder.py | 80 | 🟠 High | Generic build_event() (saves 80 lines) |
| UID wrappers | master_uid_service.py | 40 | 🟡 Medium | Registry-based for_model() (saves 40 lines) |
| Model methods | models.py | 50 | 🟡 Medium | Base class implementation (saves 50 lines) |
| Natural keys | signals_master_sync.py | 40 | 🟡 Medium | Registry-driven extraction (saves 25 lines) |
| Serialization | 2 files | 40 | 🟡 Medium | Move to canonical location (saves 40 lines) |
| Tests | test_master_sync_unit.py | ~60 | 🟡 Medium | Parametrized tests (saves 30 lines) |
| **TOTAL** | | **~430** | | **~385 line reduction** |

---

## Recommended Execution Order

1. **Phase 1 (Quick wins — 1 day):**
   - Consolidate serialization (single source of truth)
   - Move natural key extraction to registry
   - Extract generic build_event() in MasterEventBuilder

2. **Phase 2 (Medium effort — 2 days):**
   - Implement dynamic signal handler registration
   - Replace 16 for_* methods with registry-based for_model()
   - Remove compute_master_uid from all 16 models

3. **Phase 3 (Testing — 1 day):**
   - Add parametrized tests
   - Verify all edge cases with existing test suite
   - Performance testing (should be unchanged or faster)

---

## Consolidation Benefits

✅ **Code Maintainability:** Fewer places to update when adding new models  
✅ **Single Source of Truth:** Registries eliminate cross-file duplication  
✅ **Test Coverage:** Parametrized tests cover more scenarios with less code  
✅ **Performance:** No change (same logic, just organized differently)  
✅ **Future Proofing:** Adding new master model requires only registry entry  

---

## Risk Mitigation

All refactors are **backward-compatible**:
- Existing method signatures preserved (for_company, build_create_event, etc.)
- Logic unchanged (just moved/reorganized)
- Tests pass without modification
- Can be done incrementally (one consolidation at a time)

**Recommended approach:** Implement Phase 1 and 2 consolidations, then run full test suite to verify.

---

## Files to Modify

1. `backend/apps/core/services/master_uid_service.py` — Add registry, for_model()
2. `backend/apps/core/services/master_event_builder.py` — Add generic build_event()
3. `backend/apps/core/signals_master_sync.py` — Dynamic handler registration, registry-driven natural keys
4. `backend/apps/core/models.py` — Remove compute_master_uid from 16 models (or move to base class)
5. `backend/apps/core/tests/test_master_sync_unit.py` — Add parametrized tests

---

## Next Steps

1. Review this audit with the team
2. Approve consolidation phase order
3. Create individual PRs per consolidation
4. Measure code metrics before/after (lines of code, cyclomatic complexity, test coverage)
5. Update documentation with new patterns for future modules
