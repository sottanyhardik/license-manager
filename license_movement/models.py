from django.db import models

# Create your models here.
SEND = 'S'
RECEIVED = 'R'

MOVEMENT_TYPE = (
    (SEND, 'Send'),
    (RECEIVED, 'Received'),
)

COURIER = 'C'
PERSON = 'P'

MEDIUM_TYPE = (
    (COURIER, 'Courier'),
    (PERSON, 'Person'),
)


class LicenseMovementModel(models.Model):
    license_number = models.CharField(max_length=15)
    type = models.CharField(max_length=2, choices=MOVEMENT_TYPE)
    license_from = models.CharField(max_length=255)
    license_to = models.CharField(max_length=255)
    purpose = models.CharField(max_length=255)
    medium = models.CharField(max_length=2, choices=MEDIUM_TYPE)
    courier_or_person_name = models.CharField(max_length=255)
    courier_or_person_number = models.CharField(max_length=255)
    admin_search_fields = ('license_number',)

    def __str__(self):
        return "{}".format(self.license_number, self.type, self.license_to)
