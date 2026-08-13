# AGENT 5 — Master Media Synchronization Audit

## Executive Summary

**Date:** 2026-08-12  
**Scope:** All Master models with media fields  
**Critical Finding:** Master data and media are **NOT atomically synchronized**. Master data can propagate to remote servers while media files remain stranded locally.

CompanyModel is the **only Master with media fields** (logo, signature, stamp), but these fields are:
- Excluded from sync event payloads (file/image fields explicitly skipped)
- Not tracked in MasterMediaMetadata (model exists but unused in production)
- Not validated on upload (MIME type, file size)
- Not verified on download (no SHA256 verification)
- Not cleaned up on deletion (no deletion signals)
- Not covered by atomic transaction boundaries

---

## 1. Media-Capable Masters

### 1.1 CompanyModel — 3 ImageFields

**Table:** `core_companymodel`  
**Natural Key:** `iec` (IEC code)  
**Sync Identity:** `master_uid` (deterministic UUID based on IEC)

**Media Fields:**

| Field      | Type       | Storage Path           | Upload Function       | Current Status   |
|------------|------------|------------------------|-----------------------|------------------|
| `logo`     | ImageField | `companies/{id}/{fname}` | `company_upload_path` | Unsynced         |
| `signature` | ImageField | `companies/{id}/{fname}` | `company_upload_path` | Unsynced         |
| `stamp`    | ImageField | `companies/{id}/{fname}` | `company_upload_path` | Unsynced         |

**Storage Implementation:**

```python
# backend/apps/core/models.py:76-78
def company_upload_path(instance, filename):
    return f"companies/{instance.id}/{filename}"
```

Files are stored on local filesystem under `MEDIA_ROOT/companies/{company_id}/`.

---

## 2. Non-Master Models with Media (Excluded from Sync Scope)

For completeness, the codebase also includes media in these non-Master models:

### 2.1 User (Django Auth Model)

**Field:** `avatar` (ImageField)  
**Upload Path:** Django's default  
**Deletion Signals:** ✓ Implemented
- `delete_avatar_on_user_delete` (post_delete)
- `delete_old_avatar_on_change` (pre_save)

### 2.2 BillOfEntryModel

**Field:** `boe_pdf_copy` (FileField)  
**Upload Path:** `boe_copies/`  
**Deletion Signals:** ✗ Not implemented  
**Media Access:** Protected by `ProtectedMediaView` (role-based auth)

### 2.3 TradeModel (LicenseTrade)

**Field:** `purchase_invoice_copy` (FileField)  
**Upload Path:** `trade/purchase_invoices/`  
**Deletion Signals:** ✗ Not implemented  
**Media Access:** Protected by `ProtectedMediaView` (role-based auth)

### 2.4 InvoiceEntity (Non-Master, non-sync)

**Fields:**
- `logo` (ImageField, `entity_logos/`)
- `signature` (ImageField, `entity_signature/`)
- `stamp` (ImageField, `entity_stamp/`)

**Deletion Signals:** ✗ Not implemented

---

## 3. Critical Gaps: Media Synchronization

### 3.1 Payload Serialization Excludes Media

**Location:** `backend/apps/core/services/master_event_builder.py:195-223`

When a Master change event is created, the `_serialize_instance()` method explicitly skips file/image fields:

```python
# Lines 196-199: Skip relations
if field.many_to_one or field.many_to_many or field.one_to_many:
    continue

# Lines 204-207: Comment states intent
# Skip File/image fields
# Large binary data

elif hasattr(value, '__dict__'):
    # Skip complex objects (will cause serialization errors)
    continue
```

**Impact:**
- When `CompanyModel` is created/updated, `logo`, `signature`, `stamp` are **never included** in the event payload
- Remote servers receive only text/numeric fields
- Media files remain locally, creating data inconsistency

**Evidence:** `master_sync_base.py:175-213` (get_sync_payload) uses identical skip logic.

### 3.2 MasterMediaMetadata Model Exists but Unused

**Location:** `backend/apps/core/models.py:1175-1237`

The model is defined and migrated (0016) but:

```python
class MasterMediaMetadata(models.Model):
    media_uid = UUIDField(unique=True, db_index=True)
    master_uid = UUIDField(db_index=True)
    media_field = CharField(max_length=100)  # 'logo', 'signature', 'stamp'
    filename = CharField(max_length=255)
    content_type = CharField(max_length=100)
    size = BigIntegerField()
    sha256 = CharField(max_length=64, unique=True, db_index=True)
    synchronized_at = DateTimeField(null=True, blank=True)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

**Production Usage:** Only in tests (`test_master_sync_unit.py:243-274`)
- No signals populate this table on CompanyModel upload
- No views query this table
- No sync code reads `media_uid`, `sha256`, or `synchronized_at`

---

## 4. Validation Gaps

### 4.1 No MIME Type Validation on Upload

**Finding:** CompanyModel's ImageFields use Django's default ImageField validator only.

**Missing:**
- No whitelist enforcement (e.g., PNG, JPG only)
- No content-type inspection (file extension can be spoofed)
- No rejection of SVG/WEBP/other formats
- MasterMediaMetadata.content_type is defined but never populated

**Recommended Approach:**
```python
# What should be done but isn't:
def validate_company_image(file):
    allowed = {'image/png', 'image/jpeg', 'image/jpg'}
    content_type = file.content_type or mimetypes.guess_type(file.name)[0]
    if content_type not in allowed:
        raise ValidationError(f"Invalid image type: {content_type}")
```

### 4.2 No File Size Validation

**Finding:** No upload size limit enforced on CompanyModel media fields.

**Risk:**
- Arbitrarily large files accepted (DOS)
- Storage exhaustion possible
- Sync transfer becomes impractical (no streaming, full files in memory)

**Missing:** Max file size config (both per-field and per-master)

### 4.3 No Content Inspection

No verification that:
- Uploaded file is actually an image (magic bytes check)
- File is not corrupted or truncated
- File doesn't contain embedded code/malware

---

## 5. File Integrity & Verification

### 5.1 No SHA256 Computation on Upload

**Finding:** CompanyModel upload does not compute file hash.

**Impact:**
- No deduplication possible (identical files stored multiple times)
- No corruption detection
- No remote verification possible
- MasterMediaMetadata.sha256 field never populated

**Missing Mechanism:**

```python
# What should be done on upload:
import hashlib

def compute_file_sha256(file):
    hasher = hashlib.sha256()
    for chunk in file.chunks():
        hasher.update(chunk)
    return hasher.hexdigest()
```

### 5.2 No SHA256 Verification on Download

**Finding:** `ProtectedMediaView` serves company media without integrity check.

**Code:** `backend/apps/core/views/media.py:82-129`
- Lines 37-79: Custom role-based access control (companies not included)
- Lines 95-115: File path validation but no content verification
- No SHA256 header or checksum validation

**Missing:** `ETag` or `X-File-Sha256` response header for client-side verification.

---

## 6. Deletion Flow

### 6.1 No Deletion Signals for CompanyModel Media

**Finding:** CompanyModel has no signal handlers for media cleanup.

**Comparison (User Model):**
```python
# backend/apps/accounts/signals.py works correctly:
@receiver(post_delete, sender=User)
def delete_avatar_on_user_delete(sender, instance, **kwargs):
    if instance.avatar:
        instance.avatar.delete(save=False)

@receiver(pre_save, sender=User)
def delete_old_avatar_on_change(sender, instance, **kwargs):
    # Compare old vs new avatar and delete old
```

**Missing for CompanyModel:**
- No `post_delete` handler → When company deleted, logo/signature/stamp remain on disk (orphaned)
- No `pre_save` handler → When logo is replaced, old file remains (orphaned)
- No cleanup in soft-delete flow (`mark_deleted()`)

**Risk:** Storage bloat, stale files referenced in backups.

### 6.2 Cascading Deletion

**Question:** What if CompanyModel is soft-deleted?

```python
# backend/apps/core/master_sync_base.py:126-142
def mark_deleted(self, user=None):
    self.deleted = True
    self.deleted_at = timezone.now()
    self.tombstone_version = self.master_version
    self.save()
```

**Finding:** Soft-delete does NOT delete media files.

**Impact:**
- Deleted companies' media remains accessible if path is guessed
- No automatic cleanup of tombstoned records' media

---

## 7. Duplicate & Missing Media Detection

### 7.1 No Duplicate Detection

**Scenario:** User uploads same logo twice under different filenames:

```
companies/123/logo.png (sha256: abc123)
companies/123/company_logo.png (sha256: abc123)
```

**Current Behavior:** Both stored (2x disk usage)  
**Ideal Behavior:** Second upload reuses first file  
**Why Missing:** No SHA256 computation, no deduplication logic

### 7.2 No Missing Media Detection

**Scenario:** Database record exists but file deleted from disk:

```
CompanyModel.id=123, logo='logo.png'
→ /media/companies/123/logo.png DELETED
```

**Current Behavior:** 
- API returns record successfully
- `ProtectedMediaView.get()` returns 404 (silent fail)
- No audit trail or alert

**Missing:** Audit command to detect orphans:
```bash
./manage.py audit_media --check-missing --check-orphan
```

---

## 8. Upload/Download/Retry Flow

### 8.1 Upload Flow (Implicit)

**Mechanism:** Django's standard multipart form handling via `MultiPartParser`

**ViewSet:** `MasterViewSet` (inherited by CompanyViewSet)
```python
# backend/apps/core/views/master_view.py
parser_classes = [MultiPartParser, FormParser, JSONParser]

def perform_update(self, serializer):
    user = getattr(self.request, "user", None)
    extra = {}
    if user and getattr(user, "is_authenticated", False):
        extra["modified_by"] = user
    serializer.save(**extra)
```

**Problem:** No explicit media handler, no validation pre-save, no metadata population.

### 8.2 Download Flow

**Mechanism:** `ProtectedMediaView` (lines 82-129)

**For Company Media:** NOT explicitly handled
```python
# backend/apps/core/views/media.py:37-79
def _required_read_roles(rel_path):
    if rel_path.startswith("licenses/"):
        # ...
    if rel_path.startswith("boe_copies/"):
        # ...
    if rel_path.startswith("trade/"):
        # ...
    return None  # <- Companies default to "any authenticated user"
```

**Finding:** Company media is served to ANY authenticated user (no role check).

### 8.3 No Retry Mechanism

**Finding:** No exponential backoff, queue, or retry logic for media sync.

**Missing:** 
- `MasterMediaSyncOutbox` table (like `MasterSyncOutbox` for data)
- Async task to push media to remote servers
- Cursor tracking for media sync progress
- Failed transfer recovery

**Impact:** If remote sync is attempted, failed media transfers are unrecoverable.

---

## 9. Atomic Synchronization

### 9.1 Data/Media Not Atomic

**Scenario:** CompanyModel update with new logo

**Current Flow:**
```
1. CompanyModel save() called
   ├─ Form parses multipart data
   ├─ Serializer validates fields
   ├─ Image file saved to disk
   └─ CompanyModel.logo set to new path
   
2. Transaction commits (master_uid, name, etc. sync to outbox)
   ├─ Signal handler creates MasterSyncOutbox
   ├─ Payload sent to remote servers
   └─ Master UID propagates (logo field excluded)

3. [RACE] Image file NOT in sync
   └─ Remote servers have CompanyModel record
   └─ But logo file still local
```

**Risk:** Partial consistency — remote servers can't display logo.

### 9.2 Missing Atomic Boundary

**Ideal Flow:**
```
BEGIN TRANSACTION
  1. Validate image (MIME, size, content)
  2. Compute SHA256
  3. Save to disk
  4. Create MasterMediaMetadata record
  5. Update CompanyModel.logo (just path, not the file)
  6. Create outbox entry WITH media manifest
COMMIT TRANSACTION
```

**Current:** File saved independently, outbox created in separate transaction.

---

## 10. Access Control

### 10.1 Company Media Not Protected

**Finding:** Company media (logo, signature, stamp) are served to ANY authenticated user.

**Code:** `ProtectedMediaView._required_read_roles()` (lines 37-79) returns `None` for `companies/...` paths
```python
def _required_read_roles(rel_path):
    if rel_path.startswith("companies/"):
        return None  # <- No role check
    # ...
```

**Impact:** 
- Any user can download any company's signature (PII/legally-binding image)
- No audit trail for access
- No per-company access restriction

**Ideal:** Role-based access like BillOfEntryPermission/TradePermission:
```python
if rel_path.startswith("companies/"):
    from apps.core.models import CompanyModel
    company_id = rel_path.split('/')[1]
    return CompanyPermission.required_roles_for_read
```

---

## 11. Storage Configuration

**Current Settings:**

```python
# backend/lmanagement/settings.py:170-171
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

**Missing Configurations:**
- `DATA_UPLOAD_MAX_MEMORY_SIZE` (default 2.5MB global limit)
- No per-field file size limits
- No storage backend abstraction (S3/GCS ready)
- No separate staging/archive structure

---

## 12. Master Sync Integration Points

### 12.1 Signal Handlers

**Current:** Signals created for all 16 Masters, but none handle media.

```python
# backend/apps/core/signals_master_sync.py:160-165
@receiver(post_save, sender=CompanyModel, dispatch_uid="company_model_sync")
def on_company_save(sender, instance, created, **kwargs):
    if created:
        create_outbox_entry(instance, 'CREATE')
    else:
        create_outbox_entry(instance, 'UPDATE')
```

**Missing:** Media metadata update in signal.

### 12.2 Event Builder

**Location:** `backend/apps/core/services/master_event_builder.py:166-223`

**Lines 177-179 (Comment):**
```python
# Excludes:
# - ForeignKey/M2M relations
# - File/image fields
# - Large binary data
```

**Finding:** Deliberate exclusion, not accidental oversight.

**Question:** Was binary exclusion by design (deferred Phase), or oversight?

---

## 13. Test Coverage

### 13.1 MasterMediaMetadata Tests

**Location:** `backend/apps/core/tests/test_master_sync_unit.py:243-273`

```python
class TestMediaHandling(TestCase):
    """Test media SHA256 and corruption detection."""

    def test_media_metadata_creation(self):
        """Media metadata can be created."""
        media = MasterMediaMetadata.objects.create(...)
```

**Finding:** Tests verify schema only, NOT actual sync behavior.

- No test for media upload
- No test for media inclusion in event
- No test for media deletion
- No test for SHA256 computation

**Missing:** Integration tests for full media lifecycle.

---

## 14. Findings Summary

| Finding | Severity | Category | Status |
|---------|----------|----------|--------|
| Media excluded from sync payload | 🔴 Critical | Atomicity | Unaddressed |
| No MIME type validation | 🟡 High | Security | Unaddressed |
| No file size validation | 🟡 High | Security | Unaddressed |
| No SHA256 computation | 🟡 High | Integrity | Unaddressed |
| No SHA256 verification on download | 🟡 High | Integrity | Unaddressed |
| No deletion signals (Master media) | 🟡 High | Lifecycle | Unaddressed |
| No duplicate detection | 🟠 Medium | Optimization | Unaddressed |
| No missing media detection | 🟠 Medium | Audit | Unaddressed |
| Company media not access-controlled | 🟡 High | Security | Unaddressed |
| No retry/recovery for media sync | 🟡 High | Reliability | Unaddressed |
| MasterMediaMetadata unused | 🟡 High | Debt | Planned but incomplete |
| No atomic data+media boundary | 🔴 Critical | Consistency | Unaddressed |

---

## 15. Recommendations (ROADMAP)

### Phase 1: Data Integrity (Prerequisite)
- Implement SHA256 computation on upload
- Add MIME type whitelist validation
- Add file size limits (configurable)
- Populate MasterMediaMetadata on save

### Phase 2: Deletion Safety
- Add deletion signals for CompanyModel
- Implement soft-delete media cleanup
- Add orphan detection audit command

### Phase 3: Access Control
- Extend ProtectedMediaView to cover company media
- Add role-based access for company assets
- Implement access audit logging

### Phase 4: Sync Integration
- Include media_uid/sha256 in event payloads
- Extend MasterSyncOutbox for media references
- Implement media sync task (async)
- Add media cursor tracking

### Phase 5: Reliability
- Implement media retry queue
- Add offline recovery mechanism
- Implement deduplication by SHA256
- Add media sync health checks

---

## 16. Conclusion

**Master data and media are NOT atomically synchronized.** The infrastructure for media tracking exists (MasterMediaMetadata model, upload paths, deletion pattern) but is **incomplete and unused in production**.

CompanyModel is the only Master with media, and its media:
- ❌ Are never synchronized to remote servers
- ❌ Are not validated on upload
- ❌ Are not verified on download
- ❌ Are not cleaned up on deletion
- ❌ Are not access-controlled
- ❌ Are not deduplicated
- ❌ Are not audited for integrity

The codebase has proven patterns (User avatar signals, BillOfEntryModel PDF protection, ProtectedMediaView) but they are **not applied consistently to Master media**.

**Recommendation:** Prioritize Phase 1 (data integrity) and Phase 4 (sync integration) before any multi-server Master synchronization goes live. Without atomic data+media sync, consistency guarantees cannot be maintained.

---

## Appendix A: Files Reviewed

**Models:**
- `backend/apps/core/models.py` (CompanyModel, MasterMediaMetadata)
- `backend/apps/accounts/models.py` (User.avatar)
- `backend/apps/bill_of_entry/models.py` (BillOfEntryModel.boe_pdf_copy)
- `backend/apps/trade/models.py` (TradeModel.purchase_invoice_copy)

**Services & Sync:**
- `backend/apps/core/master_sync_base.py` (get_sync_payload)
- `backend/apps/core/signals_master_sync.py` (signal handlers)
- `backend/apps/core/services/master_event_builder.py` (_serialize_instance)

**Views & Endpoints:**
- `backend/apps/core/views/master_view.py` (MasterViewSet, upload handling)
- `backend/apps/core/views/media.py` (ProtectedMediaView)

**Signals:**
- `backend/apps/accounts/signals.py` (avatar deletion, pattern reference)

**Tests:**
- `backend/apps/core/tests/test_master_sync_unit.py` (TestMediaHandling)

**Configuration:**
- `backend/lmanagement/settings.py` (MEDIA_ROOT, MEDIA_URL)

---

**Report Generated:** 2026-08-12  
**Agent:** AGENT 5 — Media/Sync Specialist  
**Audit Status:** COMPLETE
