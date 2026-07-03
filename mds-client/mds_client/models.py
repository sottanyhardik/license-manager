"""Local bookkeeping for the mirror sync.

Only ``MDSSyncState`` lives here — one small row per synced model holding the
delta cursor (``cursor`` = the ``max(modified_on)`` we've pulled through) and the
last collection ``etag`` (for cheap ``If-None-Match`` polling). The actual master
mirror tables belong to the consuming project (e.g. ``core.CompanyModel``); this
package never owns them, it only advances the cursor and upserts into them.
"""

from django.db import models
from django.utils import timezone


class MDSSyncState(models.Model):
    """Per-model sync high-water mark for the local mirror."""

    #: e.g. "core.CompanyModel" — the key into settings.MDS_MODELS.
    model_label = models.CharField(max_length=100, unique=True)

    #: ISO-8601 cursor: the greatest modified_on we have mirrored so far. Sent as
    #: ?updated_since on the next pull. Null before the first sync (full pull).
    cursor = models.CharField(max_length=64, blank=True, null=True)

    #: last collection ETag seen; sent as If-None-Match to short-circuit unchanged
    #: models with a 304 (no rows transferred).
    etag = models.CharField(max_length=128, blank=True, null=True)

    #: cursor for the change feed (deletes) — ``at`` of the last applied change.
    changes_cursor = models.CharField(max_length=64, blank=True, null=True)

    last_synced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "MDS sync state"
        verbose_name_plural = "MDS sync state"
        ordering = ["model_label"]

    def __str__(self):
        return f"{self.model_label} @ cursor={self.cursor or 'initial'}"

    def touch(self):
        self.last_synced_at = timezone.now()
