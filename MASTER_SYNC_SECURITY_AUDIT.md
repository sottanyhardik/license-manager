# Master Sync Security Audit Report
**Date:** 2026-08-12  
**Auditor:** Security Engineer (AGENT 6)  
**System:** License Manager Master Synchronization API (Phase 19/21)

---

## Executive Summary

The Master Sync API implements server-to-server authentication via HMAC-SHA256 signatures with timestamp and nonce verification for replay attack protection. While the **cryptographic foundations are sound**, the implementation has **critical deployment and architectural defects** that expose master data to unauthorized access.

**Overall Risk Level: CRITICAL (9.5/10)**

---

## 1. Server Authentication (API Tokens & HMAC)

### ✅ STRENGTHS

**HMAC-SHA256 Implementation** (backend/apps/core/services/master_sync_security.py)
- Correct use of constant-time comparison: `hmac.compare_digest(expected_signature, received_signature)`
- Canonical input construction prevents signature bypass:  
  ```
  METHOD|PATH|PAYLOAD_HASH|TIMESTAMP|NONCE
  ```
- Payload hash (SHA256) prevents body tampering
- Nonce included in signature prevents signature reuse

**Authentication Header Parsing**
- Bearer token format enforced: `Bearer SERVER_A:<signature>`
- Server ID extracted from token header
- Signature verified before authorization lookup

### ❌ CRITICAL ISSUES

#### 1.1: Endpoints NOT Registered in URL Router
**Severity: CRITICAL (9.8/10)**  
**Location:** backend/lmanagement/urls.py (lines 30-54)  
**Finding:**
```
Missing URL patterns for:
- /api/master-sync/events/ (POST)
- /api/master-sync/events/ (GET)
- /api/master-sync/ack/ (POST)
- /api/master-sync/cursor/ (GET)
- /api/master-sync/health/ (GET)
```

**Impact:**
- API endpoints are **DEAD CODE** — defined in views/master_sync.py but never wired up
- Cannot be accessed even if authentication was perfect
- Suggests incomplete implementation; no active Master Sync yet

**Failure Scenario:**
Any attempt to POST to `/api/master-sync/events/` returns 404 (JSON). Outbox events created by signals_master_sync.py accumulate in the database with no push mechanism.

**Recommendation:**
```python
# Add to backend/apps/core/urls.py or create backend/apps/core/sync_urls.py
from .views.master_sync import (
    MasterSyncEventsView, MasterSyncFetchView, MasterSyncAckView,
    MasterSyncCursorView, MasterSyncHealthView
)

urlpatterns = [
    path('master-sync/events/', MasterSyncEventsView.as_view(), name='master-sync-events'),
    path('master-sync/events/<str:after>/', MasterSyncFetchView.as_view(), name='master-sync-fetch'),
    path('master-sync/ack/', MasterSyncAckView.as_view(), name='master-sync-ack'),
    path('master-sync/cursor/', MasterSyncCursorView.as_view(), name='master-sync-cursor'),
    path('master-sync/health/', MasterSyncHealthView.as_view(), name='master-sync-health'),
]
```

#### 1.2: Secret Token Storage in Plain Text
**Severity: CRITICAL (9.5/10)**  
**Location:** backend/apps/core/models.py, lines 841–844  
**Finding:**
```python
secret_token = models.CharField(
    max_length=255,
    blank=True,
    help_text="HMAC secret for server-to-server authentication"
)
```

**Impact:**
- Secrets stored **unencrypted in database**
- Any database backup, accidental export, or SQL injection reveals all server secrets
- No field-level encryption
- Django admin UI exposes secret in plaintext forms

**Failure Scenario:**
1. Attacker gains read access to PostgreSQL (compromised backup, or via SQL injection)
2. Extracts `MasterSyncServer.secret_token` for all servers
3. Can forge valid HMAC signatures and inject malicious events
4. All server-to-server master data compromised

**Recommendation:**
```python
from django.contrib.postgres.fields import EncryptedField  # or use django-encrypted-model-fields

secret_token = EncryptedField(
    max_length=255,
    blank=True,
    help_text="HMAC secret (encrypted at rest)"
)
```

Or use environment variables + init-time lookup (no database storage).

#### 1.3: Server ID Extracted from Untrusted Authorization Header
**Severity: HIGH (8/10)**  
**Location:** backend/apps/core/views/master_sync.py, lines 64–67  
**Finding:**
```python
# Extract server_id from auth header to find server
server_id = None
if auth_header.startswith('Bearer '):
    server_id = auth_header[7:].split(':')[0]
```

**Impact:**
- `server_id` derived from client-supplied data before secret lookup
- Attacker can claim any server ID; if the claimed server ID doesn't exist, returns 401
- If server ID matches an inactive/deleted server, possible information leak

**Failure Scenario:**
1. Attacker sends `Authorization: Bearer LEGIT_SERVER:fake_sig`
2. Code extracts `server_id = "LEGIT_SERVER"`
3. Database lookup succeeds; code attempts signature verification
4. Attacker doesn't know the secret, so signature fails → 401 ✓ (correct here)
5. But if server ID is stored in plaintext, attacker who once saw the database can forge the signature

**Recommendation:** **Mitigated by 1.2** (encrypt secrets at rest). Current server ID extraction is acceptable once secrets are protected.

### ⚠️ DESIGN CONCERNS

#### 1.4: Timestamp Tolerance = 5 Minutes
**Severity: MEDIUM (6/10)**  
**Location:** backend/apps/core/services/master_sync_security.py, line 84  
**Finding:**
```python
timestamp_tolerance: int = 300,  # 5 minutes
```

**Impact:**
- 5 minutes is wide for stateless APIs
- Synchronization clock skew between servers must be < 5 min or requests rejected
- Legitimate slow network requests within 5-min window still vulnerable to replay if nonce cache is lost

**Recommendation:**
Reduce to 60–120 seconds unless clock sync is documented as unreliable.

---

## 2. Authorization (Which Servers Can Sync Which Masters?)

### ❌ NO AUTHORIZATION LOGIC IMPLEMENTED
**Severity: CRITICAL (9.5/10)**  
**Finding:**
All five Master Sync endpoints have **zero authorization checks**:

- **MasterSyncEventsView.post()** (lines 28–135)  
  ✓ Verifies HMAC signature  
  ✗ **Does NOT check:** Can `SERVER_A` write to `Master_X` in this database instance?  
  ✗ **Does NOT check:** Is the origin server trusted for this model type?

- **MasterSyncFetchView.get()** (lines 143–203)  
  ✓ Returns pending events  
  ✗ **Does NOT check:** Can `SERVER_B` read master data for `Model_Y`?  
  ✗ **Does NOT check:** Should sensitive masters (e.g., company banking info) be shared?

- **MasterSyncAckView.post()** (lines 211–255)  
  ✓ Records delivery acknowledgment  
  ✗ **Does NOT check:** Can `SERVER_C` ack events it didn't receive?  
  ✗ **Does NOT check:** Can a server ack another server's events?

- **MasterSyncCursorView.get()** (lines 263–292)  
  ✓ Returns sync cursor  
  ✗ **Does NOT check:** Should remote servers know this server's internal sync state?

- **MasterSyncHealthView.get()** (lines 300–343)  
  ✓ Returns health metrics  
  ✗ **Does NOT check:** Should external servers read pending event counts?

**Failure Scenario:**
```
Server A's admin (attacker) obtains Server B's secret via database breach.
- Forges request: POST /api/master-sync/events/ with Bearer SERVER_B:<valid_sig>
- Injects DELETE event for all Company masters (model='CompanyModel', operation='DELETE')
- MasterSyncEventsView accepts it (signature valid, no authz checks)
- Events land in Server B's inbox → processed → all companies deleted from Server B ✗
```

**Recommendation:**

1. **Define Server Topology:**
   - Which servers trust which? (e.g., `SERVER_A` pushes to `SERVER_B` and `SERVER_C`, but `SERVER_D` is read-only)
   - Store allowed peer list in database or config

2. **Add Authorization Layer:**
   ```python
   class MasterSyncEventsView:
       def post(self, request):
           ...
           # Verify HMAC (existing)
           is_valid, server_id, error = verify_hmac_signature(...)
           if not is_valid:
               return Response(..., status=401)
           
           # NEW: Check if this server is allowed to write
           from backend.apps.core.models import MasterSyncServer
           server = MasterSyncServer.objects.get(server_id=server_id)
           
           if not server.can_write:  # Add field to model
               return Response({'error': 'Server not authorized to write'}, status=403)
           
           model_name = data.get('model_name')
           if not server.allowed_models.filter(name=model_name).exists():  # M2M relationship
               return Response(
                   {'error': f'Server not authorized for {model_name}'}, 
                   status=403
               )
           
           # Continue with inbox creation...
   ```

3. **Audit Log Every Authorization Decision** (see section 6)

---

## 3. Secrets Management

### ❌ CRITICAL: Secrets Stored Plaintext in Database
**Severity: CRITICAL (9.8/10)**  
*See section 1.2*

### ⚠️ CONCERN: No Key Rotation Mechanism
**Severity: MEDIUM (7/10)**  
**Finding:**
- `MasterSyncServer.secret_token` has no versioning
- No `secret_token_previous`, `secret_token_rotated_at`, etc.
- Rotating a secret while remote servers are offline breaks those servers

**Recommendation:**
Support dual-secret validation:
```python
def verify_hmac_signature(..., server_secret, server_secret_previous=None):
    # Try current secret
    is_valid = hmac.compare_digest(expected_sig, received_sig)
    if is_valid:
        return True, server_id, None
    
    # Try previous secret (grace period during rotation)
    if server_secret_previous:
        is_valid_prev = hmac.compare_digest(expected_sig_prev, received_sig)
        if is_valid_prev:
            return True, server_id, None
    
    return False, server_id, "Invalid signature"
```

### ⚠️ CONCERN: Environment Variables Not Used
**Severity: MEDIUM (6.5/10)**  
**Finding:**
Secrets are always stored in database (MasterSyncServer model). No support for env var override.

**Recommendation:**
```python
def get_server_secret(server_id):
    # Try environment variable first
    env_key = f"MASTER_SYNC_SECRET_{server_id.upper()}"
    env_secret = os.getenv(env_key)
    if env_secret:
        return env_secret
    
    # Fallback to database (encrypted)
    try:
        server = MasterSyncServer.objects.get(server_id=server_id)
        return server.secret_token  # encrypted
    except MasterSyncServer.DoesNotExist:
        return None
```

---

## 4. Request Validation (Payload Shape & Field Types)

### ✅ STRENGTHS

**Schema Validation** (backend/apps/core/services/master_sync_security.py, lines 177–244)
- Whitelist of allowed models enforced (lines 194–200)
- Whitelist of allowed operations (CREATE, UPDATE, DELETE) enforced
- JSON serializability check prevents pickle exploits
- UUID format validation for `master_uid`
- Integer type check for `version`

**Payload Size Limits**
- Not explicitly enforced, but implied by query limit: `limit = min(limit, 1000)` (line 176)

### ⚠️ MEDIUM ISSUES

#### 4.1: Missing Required Field Validation in Inbox POST
**Severity: MEDIUM (6.5/10)**  
**Location:** backend/apps/core/views/master_sync.py, lines 100–110  
**Finding:**
```python
# Validate payload schema
data = request.data
model_name = data.get('model_name')
operation = data.get('operation')

is_valid_schema, schema_error = validate_payload_schema(data, model_name, operation)
```

But `validate_payload_schema()` expects the outer `request.data` dict, not the `payload` field inside it.

**Checking the function** (services/master_sync_security.py, lines 221–227):
```python
required_fields = {'master_uid', 'version', 'payload'}
if not isinstance(payload, dict):
    return False, "Payload must be a dict"

for field in required_fields:
    if field not in payload:  # ← payload = request.data (outer dict)
        return False, f"Missing required field: {field}"
```

This validates the outer `request.data`, not the nested `payload` field. The nested `payload` is never schema-validated for its contents.

**Failure Scenario:**
```json
POST /api/master-sync/events/
{
    "event_uid": "EVT123",
    "master_uid": "abc...",
    "model_name": "CompanyModel",
    "operation": "UPDATE",
    "version": 5,
    "payload": {
        "iec": "1234",
        "name": null,  // Missing required field
        "bank_account": "attacker_injected_data"
    },
    "payload_hash": "..."
}
```
Signature validates, schema validates (outer dict is correct), but `payload.name` is null.
When applied to the model, `name` field becomes null → data corruption or silent rejection depending on model constraints.

**Recommendation:**
```python
def validate_payload_schema(data, model_name, operation):
    # ...existing checks...
    
    # Validate the payload field's contents
    payload_field = data.get('payload', {})
    if not isinstance(payload_field, dict):
        return False, "payload field must be a dict"
    
    # Model-specific field validation
    if model_name == 'CompanyModel':
        required_payload_fields = {'iec', 'name', 'master_uid', 'master_version'}
        for field in required_payload_fields:
            if field not in payload_field:
                return False, f"Missing payload field: {field}"
        
        if not isinstance(payload_field.get('iec'), str):
            return False, "payload.iec must be string"
    
    # ...etc for other models...
    
    return True, None
```

#### 4.2: No Content-Length or Payload Size Limit
**Severity: MEDIUM (7/10)**  
**Location:** backend/apps/core/views/master_sync.py, lines 28–135  
**Finding:**
No check on request body size. Django default is 2.5 MB; attacker can send 2.5 MB events repeatedly.

**Failure Scenario:**
```
for i in range(100):
    POST /api/master-sync/events/ (2.5 MB invalid JSON)
    → Each parsed into inbox entry
    → OutOfMemory or disk full on inbox table
```

**Recommendation:**
```python
from django.http import HttpResponseBadRequest

def post(self, request):
    # Check request size (e.g., 10 MB max per event)
    content_length = int(request.META.get('CONTENT_LENGTH', 0))
    if content_length > 10 * 1024 * 1024:  # 10 MB
        return Response(
            {'error': 'Payload too large (max 10 MB)'},
            status=status.HTTP_413_PAYLOAD_TOO_LARGE
        )
    ...
```

---

## 5. Payload Validation (SHA256 Hash Verification)

### ✅ STRENGTHS

**Hash Computation & Verification**
```python
# Builder (security.py, line 56)
payload_json = json.dumps(payload, sort_keys=True, separators=(',', ':'))
payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()

# Verifier (security.py, line 137)
payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
```
- Canonical JSON serialization (sorted keys, compact) prevents hash collision via reordering
- SHA256 is NIST-approved cryptographic hash

**Hash Usage in Signature**
- Payload hash included in canonical signature input (line 59)
- Prevents tampering with payload after signature generation

### ⚠️ MEDIUM ISSUE

#### 5.1: Hash Computed But Never Verified Against Sender's Hash
**Severity: MEDIUM (6.5/10)**  
**Location:** backend/apps/core/views/master_sync.py, lines 83–92  
**Finding:**
```python
# Line 83: Reconstruct payload hash
payload_json = json.dumps(request.data, sort_keys=True, separators=(',', ':'))

# Line 84: Call verify_hmac_signature (which re-computes payload_hash internally)
is_valid, _, error = verify_hmac_signature(
    ...
    payload_json=payload_json,
    ...
)
```

But the incoming `request.data.get('payload_hash')` (line 123) is **never compared** against the computed hash.

**Impact:**
- HMAC signature includes payload hash, so tampering is detected
- But the explicit `payload_hash` field in the JSON is unused
- Creates confusion: why include it if it's not verified?

**Failure Scenario:**
1. Client sends payload with intentionally wrong `payload_hash` field
2. Signature still verifies (uses the correct computed hash, not the field)
3. Event accepted
4. Later reconciliation code might check the `payload_hash` field and detect mismatch

**Recommendation:**
Either:
1. **Use the field**: Verify incoming `payload_hash` == computed hash before signature check
2. **Remove the field**: Don't include it if it's redundant

Current approach is safe (signature covers the payload), but confusing.

---

## 6. Audit Logging (Who Changed What When)

### ❌ NO AUDIT LOGGING FOR SYNC EVENTS
**Severity: CRITICAL (9/10)**  
**Finding:**
```
MasterSyncEventsView.post()       — No audit log
MasterSyncFetchView.get()         — No audit log
MasterSyncAckView.post()          — No audit log
MasterSyncCursorView.get()        — No audit log
MasterSyncHealthView.get()        — No audit log
```

**Impact:**
- Incoming master changes are **silently accepted** with no record of origin
- `ActivityLogMiddleware` (settings.py, line 97) only logs authenticated users, not server-to-server API
- If a server injects malicious data, no audit trail to trace the attack

**Failure Scenario:**
1. Attacker obtains Server B's secret
2. Sends DELETE events for all Company masters
3. Server A receives events → applies them → companies deleted
4. Admin queries ActivityLog → finds no record of who deleted them (logs are keyed on `request.user`, which is None for server auth)
5. Only evidence is in MasterSyncInbox table, but no automated alerting

**Recommendation:**

Create an audit log specifically for Master Sync:

```python
# Add to models.py
class MasterSyncAuditLog(models.Model):
    ACTIONS = [
        ('RECV_EVENT', 'Received sync event'),
        ('SEND_EVENT', 'Sent sync event'),
        ('REJECT_EVENT', 'Rejected event (auth/validation failed)'),
        ('APPLY_EVENT', 'Applied event to master'),
        ('CONFLICT', 'Conflict detected'),
        ('ACK', 'Acknowledged delivery'),
    ]
    
    action = models.CharField(max_length=20, choices=ACTIONS)
    server_id = models.CharField(max_length=50, db_index=True)
    event_uid = models.CharField(max_length=255, db_index=True)
    model_name = models.CharField(max_length=255)
    operation = models.CharField(max_length=10)
    status = models.CharField(max_length=20)  # 'ACCEPTED', 'REJECTED', 'CONFLICT', etc.
    reason = models.TextField(blank=True)  # If rejected, why?
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['server_id', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
```

Then log every sync event:

```python
# In MasterSyncEventsView.post()
MasterSyncAuditLog.objects.create(
    action='RECV_EVENT',
    server_id=server_id,
    event_uid=data['event_uid'],
    model_name=model_name,
    operation=operation,
    status='ACCEPTED' if created else 'DUPLICATE',
    ip_address=get_client_ip(request),
)
```

---

## 7. Privilege Escalation Risks

### ⚠️ CONCERN: No Role/Capability Model
**Severity: HIGH (8/10)**  
**Finding:**
- All authenticated servers are treated equally
- No distinction between read-only, write, or admin servers
- No per-model authorization (e.g., "SERVER_A can only sync CompanyModel")

**Failure Scenario:**
```
1. Deploy new read-only replica: SERVER_C (for analytics)
2. Set up HMAC secret for SERVER_C
3. Server C's admin (or attacker) can POST DELETE events for **any master**
4. No way to restrict to read-only operations
```

**Recommendation:**
Add capability fields to `MasterSyncServer`:

```python
class MasterSyncServer(models.Model):
    ...
    is_read_only = models.BooleanField(default=False)  # Can't POST events
    allowed_models = models.ManyToManyField('MasterModel', blank=True)
    # If allowed_models is empty, all models are allowed (for backward compat)
    
    def can_write_model(self, model_name):
        if self.is_read_only:
            return False
        if not self.allowed_models.exists():  # All models allowed
            return True
        return self.allowed_models.filter(name=model_name).exists()
```

Then enforce in views:
```python
if not server.can_write_model(model_name):
    return Response(
        {'error': f'Not authorized to write {model_name}'},
        status=403
    )
```

---

## 8. Endpoint Exposure (External Access)

### ⚠️ CONCERN: Master Sync Endpoints Would Be Public if Registered
**Severity: HIGH (8.5/10) [Conditional — currently mitigated by not being registered]**  
**Finding:**
If endpoints are registered in `urls.py`, they would be:
- Publicly accessible on the internet (if server is exposed)
- Not behind authentication middleware (they use HMAC, not Django auth)
- Not behind CORS (CORS is for browser requests)
- Accessible from any IP address

**Failure Scenario:**
```
1. Master Sync endpoints registered in production
2. Attacker scans for /api/master-sync/ endpoints
3. Attempts HTTP POST to /api/master-sync/events/
4. If attacker obtained a server secret, can inject events
5. If attacker hasn't, gets 401, but can enumerate servers
```

**Recommendation:**

1. **IP Whitelist**: Restrict to known peer IPs via middleware

```python
# Add to middleware.py
class MasterSyncIPWhitelistMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed_ips = os.getenv('MASTER_SYNC_ALLOWED_IPS', '').split(',')
    
    def __call__(self, request):
        if request.path.startswith('/api/master-sync/'):
            client_ip = get_client_ip(request)
            if client_ip not in self.allowed_ips:
                return Response(
                    {'error': 'IP not whitelisted'},
                    status=status.HTTP_403_FORBIDDEN
                )
        return self.get_response(request)
```

2. **Separate Path**: Don't expose on public API path

```python
# In urls.py
urlpatterns = [
    # Public API (authenticated users)
    path('api/', include([
        # ... normal endpoints ...
    ]),
    
    # Master Sync (server-to-server, IP-restricted)
    path('_internal/master-sync/', include('apps.core.sync_urls')),
]
```

3. **VPC / Network Isolation**: Deploy sync endpoints on private network; external servers connect via VPN/proxy

---

## 9. Replay Attack Protection

### ✅ STRENGTHS

**Nonce Verification**
```python
# Generate (line 52)
nonce = secrets.token_hex(16)  # 32 random hex chars = 128 bits

# Verify (lines 129–134)
nonce_cache_key = f"sync_nonce:{nonce_header}"
if cache.get(nonce_cache_key):
    return False, server_id, "Nonce already used (replay attack detected)"

cache.set(nonce_cache_key, True, 300)  # TTL = 5 minutes
```

**Impact:**
- Each request includes a unique nonce
- Cache (Redis) records seen nonces for 5 minutes
- Replaying a request within 5 min is rejected ✓

### ⚠️ CONCERNS

#### 9.1: Nonce Bypass if Cache is Lost
**Severity: MEDIUM (6.5/10)**  
**Finding:**
If Redis is down or cleared, all nonces are forgotten. Attacker can replay requests.

**Failure Scenario:**
```
1. Server A sends request with nonce=abc123, payload=(delete all companies)
2. Signature and nonce verify; event accepted
3. Redis crashes; nonce cache cleared
4. Attacker intercepts the request and replays it
5. Nonce=abc123 not found in cache (cleared by crash)
6. Server accepts it again; companies deleted twice (but idempotency via event_uid prevents this)
7. However, if attacker replays within 5 min but BEFORE Redis goes down, nonce is still in cache
   → Attack is still blocked ✓
```

**Actual Risk:** Medium — relies on Redis availability. If production Redis has no HA, risk is HIGH.

**Recommendation:**
1. **Mandate Redis HA**: Use Redis Cluster or Sentinel
2. **Database Fallback**: Store nonces in PostgreSQL if cache misses

```python
# Models
class SyncNonce(models.Model):
    nonce = models.CharField(max_length=255, unique=True, db_index=True)
    expires_at = models.DateTimeField()

def verify_hmac_signature(...):
    # Try cache first
    if cache.get(nonce_cache_key):
        return False, server_id, "Nonce already used"
    
    # Try database as fallback
    if SyncNonce.objects.filter(nonce=nonce_header, expires_at__gt=now).exists():
        return False, server_id, "Nonce already used (DB)"
    
    # Record in both
    cache.set(nonce_cache_key, True, 300)
    SyncNonce.objects.create(nonce=nonce_header, expires_at=now + 300s)
```

#### 9.2: Timestamp Tolerance Enables Narrow Replay Window
**Severity: MEDIUM (6/10)**  
**Finding:**
With 5-minute tolerance, a request can be replayed at `t + 4:59` with a different nonce.

**Failure Scenario:**
```
Request sent at t=1000 (timestamp=1000, nonce=abc)
Attacker intercepts and waits 4:59 (t=1299)
Attacker re-sends with timestamp=1000 (within 5 min window)
But attacker changes nonce to xyz
→ Timestamp still validates (1299 - 1000 = 299 sec < 300)
→ Nonce is new (xyz not seen before)
→ Signature fails (attacker doesn't have secret)

But if attacker has the secret (breach), they can:
1. Modify the payload
2. Recompute payload_hash
3. Regenerate signature with modified payload
4. Use same timestamp (still within window)
5. Use new nonce

→ Request is accepted as a new event ✗
```

**Actual Risk:** CRITICAL if secrets are breached (see section 3). Medium otherwise.

**Recommendation:** Reduce timestamp tolerance to 60 seconds.

---

## 10. Nonce & Timestamp Verification

### ✅ STRENGTHS (Already covered above)
- Nonce prevents simple replay
- Timestamp prevents old-request replay (if within tolerance)
- Combined protection is sound

### ⚠️ Timestamp Tolerance Too Wide
*See section 9.2*

---

## 11. Additional Security Findings

### FINDING 1: Event ID Collision Risk
**Severity: MEDIUM (6/10)**  
**Location:** backend/apps/core/signals_master_sync.py, lines 35–40  
**Finding:**
```python
def generate_event_uid(server_id, model_name, natural_key):
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    key = f"{server_id}|{timestamp}|{model_name}|{natural_key}"
    return f"{server_id}-{timestamp}-{abs(hash(key)) % 1000000:06d}"[:255]
```

Uses Python's built-in `hash()`, which is:
- Non-cryptographic
- Randomized per process (unless PYTHONHASHSEED)
- Can collide (modulo 1,000,000)

**Failure Scenario:**
Two events created in same microsecond with same model_name and natural_key → same event_uid → idempotency treated as duplicate.

**Recommendation:**
Use UUID v5 (deterministic + cryptographic):
```python
import hashlib
import uuid

def generate_event_uid(server_id, model_name, natural_key):
    namespace = uuid.NAMESPACE_DNS  # Or create custom namespace
    key = f"{server_id}|{model_name}|{natural_key}"
    return str(uuid.uuid5(namespace, key))
```

But wait — this makes the event_uid predictable (same input = same ID). If intended, that's fine. Current code tries to include timestamp for uniqueness.

Better approach:
```python
# Use UUID4 (random) + include timestamp in separate field
event_uuid = uuid.uuid4()
event_timestamp = timezone.now()
```

### FINDING 2: No Rate Limiting on Master Sync Endpoints
**Severity: HIGH (8/10)**  
**Finding:**
REST Framework's default throttle classes (settings.py, line 213–240) apply to `/api/` routes, but:
1. Endpoints are not registered → not reached
2. If registered, throttling would apply, but no sync-specific limits

**Recommendation:**
Once endpoints are registered, add sync-specific throttle:
```python
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['sync'] = '10000/hour'

# In MasterSyncEventsView
class MasterSyncEventsView(APIView):
    throttle_scope = 'sync'
```

### FINDING 3: Inbox Processing Has No Error Handling for Malicious Data
**Severity: MEDIUM (7/10)**  
**Location:** Signal handlers (signals_master_sync.py) apply inbox events to models  
**Finding:**
When an inbox event is processed (applied to a model), no validation re-checks the payload.
An attacker could:
1. Inject event with `operation='UPDATE', master_uid='abc', payload={malicious data}`
2. Payload is applied directly to the model
3. If payload has extra fields, they're silently ignored (depending on model)
4. If payload has wrong types, Django ORM raises exception (caught and logged?)

**Recommendation:**
Always re-validate and sanitize on apply:
```python
def apply_inbox_event(inbox_event):
    try:
        # Re-validate payload against model schema
        from apps.core.services.apply_event import apply_to_model
        apply_to_model(
            model_name=inbox_event.model_name,
            operation=inbox_event.operation,
            payload=inbox_event.payload,
        )
    except ValidationError as e:
        inbox_event.status = 'REJECTED'
        inbox_event.rejection_reason = str(e)
        inbox_event.save()
        logger.warning(f"Rejected inbox event {inbox_event.event_uuid}: {e}")
```

### FINDING 4: Server Secret Accessible in Django Admin
**Severity: CRITICAL (9.5/10)**  
**Finding:**
`MasterSyncServer.secret_token` is not marked as hidden or sensitive in admin.

**Recommendation:**
```python
# In admin.py
@admin.register(MasterSyncServer)
class MasterSyncServerAdmin(admin.ModelAdmin):
    exclude = ('secret_token',)  # Never show in admin
    
    def has_change_permission(self, request, obj=None):
        # Only superusers can edit sync servers
        return request.user.is_superuser
    
    def has_view_permission(self, request, obj=None):
        # Only superusers can view
        return request.user.is_superuser
```

---

## Summary of Findings by Severity

| Severity | Count | Findings |
|----------|-------|----------|
| **CRITICAL (9–10)** | 5 | 1. Endpoints not registered (9.8), 2. Secrets plaintext (9.5), 3. No authorization (9.5), 4. No audit logging (9), 5. Admin exposure (9.5) |
| **HIGH (7–8)** | 4 | 1. IP whitelist missing (8.5), 2. Server role/capability (8), 3. Rate limit on sync (8), 4. Payload validation incomplete (6.5–7) |
| **MEDIUM (5–6.5)** | 6 | 1. Nonce/timestamp tolerance (6.5), 2. Hash field unused (6.5), 3. Size limit missing (7), 4. Event ID collision (6), 5. No inbox error handling (7), 6. Redis nonce volatility (6.5) |

---

## Remediation Roadmap

### Phase 1: Enable Endpoints (CRITICAL)
- [ ] Register Master Sync URLs in `urls.py`
- [ ] Add IP whitelist middleware
- [ ] Test endpoints with curl/Postman

### Phase 2: Encrypt Secrets (CRITICAL)
- [ ] Migrate `MasterSyncServer.secret_token` to encrypted field
- [ ] Add env var override for `MASTER_SYNC_SECRET_*`
- [ ] Rotate all existing secrets

### Phase 3: Add Authorization (CRITICAL)
- [ ] Define server topology (who trusts whom)
- [ ] Add `MasterSyncServer.allowed_models` M2M field
- [ ] Enforce authz checks in all endpoints

### Phase 4: Audit Logging (CRITICAL)
- [ ] Create `MasterSyncAuditLog` model
- [ ] Log all events, rejections, conflicts
- [ ] Set up alerting on suspicious patterns

### Phase 5: Hardening (HIGH)
- [ ] Add capability-based access control
- [ ] Implement per-model rate limits
- [ ] Add payload size limits
- [ ] Reduce timestamp tolerance to 60s
- [ ] Implement database fallback for nonce verification

### Phase 6: Testing & Validation (BEFORE PRODUCTION)
- [ ] Penetration test: Try to inject events with stolen secret
- [ ] Test: Replay attacks (nonce verification)
- [ ] Test: Timestamp tolerance edge cases
- [ ] Test: Authorization denial (invalid server, invalid model)
- [ ] Test: Audit log completeness

---

## Conclusion

The Master Sync API has **sound cryptographic foundations** (HMAC, SHA256, nonce) but **critical architectural and deployment gaps** that expose master data to unauthorized access. The **endpoints are not even registered**, making this a **dead code implementation**.

**Before enabling Master Sync in production:**

1. ✅ Encrypt secrets at rest
2. ✅ Register endpoints with IP whitelisting
3. ✅ Implement authorization (per-server, per-model)
4. ✅ Add comprehensive audit logging
5. ✅ Conduct security testing

**Current Risk: CRITICAL** — if endpoints are activated without these fixes, master data can be deleted/corrupted by attackers with database access.

---

**Audit Signed:** Security Engineer (AGENT 6)  
**Date:** 2026-08-12  
**Next Review:** After Phase 5 remediation
