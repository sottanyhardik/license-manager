"""Tiny mirror models standing in for the consumer's core.* master tables.

They carry the natural key + a couple of business fields; the sync upserts into
them by natural key exactly as it would against core.CompanyModel/PortModel.
"""

from django.db import models


class CompanyMirror(models.Model):
    iec = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    address = models.TextField(blank=True, default="")
    modified_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "mirror_app"


class PortMirror(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255, blank=True, default="")
    modified_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "mirror_app"


class NormClassMirror(models.Model):
    """A business-keyed parent (stands in for core.SionNormClassModel)."""
    norm_class = models.CharField(max_length=20, unique=True)
    modified_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "mirror_app"


class SionExportMirror(models.Model):
    """A KEYLESS child (stands in for core.SIONExportModel): synced by `uid`,
    with an FK to a parent resolved by the parent's NATURAL KEY, not by id."""
    uid = models.UUIDField(null=True, blank=True, unique=True)
    norm_class = models.ForeignKey(NormClassMirror, on_delete=models.CASCADE, related_name="exports")
    description = models.CharField(max_length=255, blank=True, default="")
    modified_on = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "mirror_app"
