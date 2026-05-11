"""
Custom middleware for License Manager
"""
from django.utils.deprecation import MiddlewareMixin


class DisableCSRFForAPIMiddleware(MiddlewareMixin):
    """
    Disable CSRF validation for API endpoints that use JWT authentication.

    This middleware exempts /api/ endpoints from CSRF validation since they use
    JWT tokens in the Authorization header instead of session-based authentication.
    """

    def process_request(self, request):
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
        return None


# ── Activity / Audit Log Middleware ──────────────────────────────────────────
import logging
import threading

_logger = logging.getLogger('core.activity')

_DOWNLOAD_KEYWORDS = ('download', 'pdf', 'excel', 'export', 'generate-bill',
                      'balance-pdf', 'balance-excel', 'generate-transfer',
                      'generate-pdf', 'generate-purchase', 'balance-report')
_UPLOAD_KEYWORDS   = ('upload', 'ledger-csv', 'upload-ledger')


def _get_client_ip(request):
    x_fwd = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_fwd:
        return x_fwd.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _infer_action(method, path):
    p = path.lower()
    if method == 'DELETE':
        return 'DELETE'
    if method in ('PUT', 'PATCH'):
        return 'UPDATE'
    if method == 'POST':
        if any(k in p for k in _UPLOAD_KEYWORDS):
            return 'UPLOAD'
        if any(k in p for k in _DOWNLOAD_KEYWORDS):
            return 'DOWNLOAD'
        return 'CREATE'
    # GET / HEAD
    if any(k in p for k in _DOWNLOAD_KEYWORDS):
        return 'DOWNLOAD'
    return 'VIEW'


def _infer_module(path):
    parts = [p for p in path.split('/') if p]
    if len(parts) >= 2 and parts[0] == 'api':
        return parts[1][:60]
    return (parts[1] if len(parts) > 1 else path)[:60]


def _infer_resource_id(path):
    for part in path.split('/'):
        if part.isdigit():
            return part
    return ''


def _write_log_entry(user, request, status_code):
    try:
        from core.models import ActivityLog
        path   = request.path
        method = request.method
        ActivityLog.objects.create(
            user=user,
            username=user.username or '',
            action=_infer_action(method, path),
            module=_infer_module(path),
            resource_id=_infer_resource_id(path),
            description=f"{_infer_action(method,path)} {_infer_module(path)}"[:500],
            endpoint=path[:500],
            method=method,
            ip_address=_get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:400],
            status_code=status_code,
        )
    except Exception:
        _logger.exception('ActivityLog: failed to write log entry')


class ActivityLogMiddleware:
    """Logs every authenticated API request asynchronously."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.path.startswith('/api/')
            and request.method != 'OPTIONS'
            and hasattr(request, 'user')
            and getattr(request.user, 'is_authenticated', False)
        ):
            threading.Thread(
                target=_write_log_entry,
                args=(request.user, request, response.status_code),
                daemon=True,
            ).start()
        return response


# ── Explicit helpers called from login / logout views ────────────────────────

def log_login(user, request):
    _explicit(user, request, 'LOGIN', 'User logged in')


def log_logout(user, request):
    _explicit(user, request, 'LOGOUT', 'User logged out')


def _explicit(user, request, action, description):
    def _do():
        try:
            from core.models import ActivityLog
            ActivityLog.objects.create(
                user=user,
                username=getattr(user, 'username', '') or '',
                action=action,
                module='auth',
                description=description,
                endpoint=getattr(request, 'path', '')[:500],
                method=getattr(request, 'method', ''),
                ip_address=_get_client_ip(request),
                user_agent=(request.META.get('HTTP_USER_AGENT', '')[:400]
                            if hasattr(request, 'META') else ''),
                status_code=200,
            )
        except Exception:
            _logger.exception('ActivityLog explicit write failed')
    threading.Thread(target=_do, daemon=True).start()
