# license/services/license_service.py
"""
Business-logic service layer for the License module.

All ORM access for License CRUD lives here — views delegate unconditionally
and never touch the ORM directly.  Every public function is wrapped in
transaction.atomic() so partial writes are rolled back on failure.
"""
import logging

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.license.models import (
    LicenseBalance,
    LicenseDetailsModel,
    LicenseFlags,
    LicenseImportItemsModel,
    LicenseNotes,
    LicenseOwnership,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# License CRUD
# ---------------------------------------------------------------------------


@transaction.atomic
def create_license(data: dict, user) -> LicenseDetailsModel:
    """
    Create a new LicenseDetailsModel plus its four satellite rows:
    LicenseBalance, LicenseFlags, LicenseNotes, LicenseOwnership.

    *data* must already be validated by the calling serializer.
    *user* is set as created_by / modified_by.
    """
    license_obj = LicenseDetailsModel.objects.create(
        **data,
        created_by=user,
        modified_by=user,
    )

    LicenseBalance.objects.create(license=license_obj)
    LicenseFlags.objects.create(license=license_obj, is_active=True)
    LicenseNotes.objects.create(license=license_obj)
    LicenseOwnership.objects.create(license=license_obj)

    logger.info("License %s created by user %s.", license_obj.pk, user)
    return license_obj


@transaction.atomic
def update_license(license_id: int, data: dict, user) -> LicenseDetailsModel:
    """
    Update only the fields present in *data* on LicenseDetailsModel.

    Raises LicenseDetailsModel.DoesNotExist if the license is not found.
    *user* is stamped onto modified_by.
    """
    license_obj = LicenseDetailsModel.objects.select_for_update().get(pk=license_id)

    for field, value in data.items():
        setattr(license_obj, field, value)
    license_obj.modified_by = user
    license_obj.save()

    logger.info("License %s updated by user %s.", license_id, user)
    return license_obj


@transaction.atomic
def delete_license(license_id: int, user) -> None:
    """
    Hard-delete a LicenseDetailsModel.

    Raises ValidationError if any import or export items are associated with
    the license — the caller must remove them first.
    Raises LicenseDetailsModel.DoesNotExist if the license is not found.
    """
    license_obj = LicenseDetailsModel.objects.get(pk=license_id)

    import_count = license_obj.import_license.count()
    export_count = license_obj.export_license.count()

    if import_count > 0 or export_count > 0:
        raise ValidationError(
            f"Cannot delete license {license_id}: "
            f"it has {import_count} import item(s) and {export_count} export item(s). "
            "Remove all items before deleting the license."
        )

    license_obj.delete()
    logger.info("License %s deleted by user %s.", license_id, user)


# ---------------------------------------------------------------------------
# Import item CRUD
# ---------------------------------------------------------------------------


@transaction.atomic
def create_import_item(license_id: int, data: dict, user) -> LicenseImportItemsModel:
    """
    Create a new LicenseImportItemsModel row for *license_id*.

    Raises LicenseDetailsModel.DoesNotExist if the license is missing.
    Raises ValidationError if serial_number conflicts.
    *data* must be pre-validated by the calling serializer.
    """
    # Verify the parent license exists
    if not LicenseDetailsModel.objects.filter(pk=license_id).exists():
        raise LicenseDetailsModel.DoesNotExist(
            f"LicenseDetailsModel with pk={license_id} does not exist."
        )

    # Validate serial_number uniqueness within the license
    serial_number = data.get("serial_number")
    if serial_number is not None and LicenseImportItemsModel.objects.filter(
        license_id=license_id, serial_number=serial_number
    ).exists():
        raise ValidationError(
            {"serial_number": f"Serial number {serial_number} already exists on this license."}
        )

    item = LicenseImportItemsModel.objects.create(
        license_id=license_id,
        **data,
    )
    logger.info(
        "Import item %s (serial %s) created for license %s by user %s.",
        item.pk,
        item.serial_number,
        license_id,
        user,
    )
    return item


@transaction.atomic
def update_import_item(item_id: int, data: dict, user) -> LicenseImportItemsModel:
    """
    Update fields on an existing LicenseImportItemsModel row.

    Raises LicenseImportItemsModel.DoesNotExist if not found.
    If serial_number changes, checks uniqueness within the same license.
    """
    item = LicenseImportItemsModel.objects.get(pk=item_id)

    new_serial = data.get("serial_number")
    if new_serial is not None and new_serial != item.serial_number:
        if LicenseImportItemsModel.objects.filter(
            license_id=item.license_id, serial_number=new_serial
        ).exclude(pk=item_id).exists():
            raise ValidationError(
                {"serial_number": f"Serial number {new_serial} already exists on this license."}
            )

    for field, value in data.items():
        setattr(item, field, value)
    item.save()

    logger.info(
        "Import item %s on license %s updated by user %s.",
        item_id,
        item.license_id,
        user,
    )
    return item


@transaction.atomic
def delete_import_item(item_id: int, user) -> None:
    """
    Hard-delete an import item.

    Raises LicenseImportItemsModel.DoesNotExist if not found.
    Note: We do not block deletion of items that have BOE or allotment
    entries — that constraint is enforced at the database level (CASCADE/PROTECT
    as defined in the legacy schema).
    """
    item = LicenseImportItemsModel.objects.get(pk=item_id)
    license_id = item.license_id
    item.delete()
    logger.info(
        "Import item %s on license %s deleted by user %s.",
        item_id,
        license_id,
        user,
    )
