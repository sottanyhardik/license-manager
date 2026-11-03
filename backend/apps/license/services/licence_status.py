"""
The licence status shown on the licence list and its accordion header.

The database has no status column on the licence, so the status is read from
the existing validity rules, in the same order as `check-validity`:

* EXPIRED when `license_expiry_date` is before today. The list's expiry filter
  and `check-validity` use this date rule. The stored `flags.is_expired` value
  is denormalised and can be stale, so it is not used here.
* INACTIVE when the stored `flags.is_active` is false.
* ACTIVE otherwise.

Other statuses, such as Cancelled, Suspended or Pending, have no stored source.
None is produced here, so none is invented.
"""

from django.utils import timezone

ACTIVE = "ACTIVE"
EXPIRED = "EXPIRED"
INACTIVE = "INACTIVE"

_LABELS = {ACTIVE: "Active", EXPIRED: "Expired", INACTIVE: "Inactive"}


def licence_status(licence) -> tuple[str, str]:
    """Return `(code, label)` for a licence. "Today" is the local date, as in `check-validity`."""
    expiry = licence.license_expiry_date
    if expiry is not None and expiry < timezone.localdate():
        code = EXPIRED
    elif not licence.is_active:
        code = INACTIVE
    else:
        code = ACTIVE
    return code, _LABELS[code]
