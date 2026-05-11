"""
Shared exception-handling utilities for DRF views.

Rules enforced here:
- Internal error detail is never returned to the API caller.
- Every exception is logged at ERROR level with a full traceback via logger.exception().
- A generic, user-safe message is returned in the response body.
"""
import logging


def api_error(message: str, exc: Exception, logger_name: str) -> dict:
    """
    Log *exc* server-side and return a safe dict for Response({'error': ...}).

    Usage:
        except Exception as e:
            return Response(api_error('Failed to generate PDF', e, __name__), status=500)
    """
    logging.getLogger(logger_name).exception(message)
    return {'error': message}


def _safe_int(value, default: int = 1, minimum: int = 1) -> int:
    """
    Parse *value* as a positive integer.  Returns *default* on None, empty, or
    non-numeric input; clamps the result to at least *minimum*.
    """
    try:
        return max(int(value), minimum)
    except (TypeError, ValueError):
        return default
