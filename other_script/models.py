from django.db import models

class SchemeType(models.TextChoices):
    RODTEP = 'RoDTEP'
    SEIS = 'SEIS'
    MEIS = 'MEIS'
    ROSCTL = 'RoSCTL'

class License(models.Model):
    number = models.CharField(max_length=100, unique=True)
    scheme = models.CharField(max_length=10, choices=SchemeType.choices)
    issue_date = models.DateField()
    expiry_date = models.DateField()
    total_value = models.DecimalField(max_digits=12, decimal_places=2)
    balance_value = models.DecimalField(max_digits=12, decimal_places=2)

class TradeParty(models.Model):
    name = models.CharField(max_length=200)
    gstin = models.CharField(max_length=15, blank=True, null=True)
    iec = models.CharField(max_length=10, blank=True, null=True)

class BuySellInvoice(models.Model):
    license = models.ForeignKey(License, on_delete=models.CASCADE)
    party = models.ForeignKey(TradeParty, on_delete=models.CASCADE)
    is_purchase = models.BooleanField()
    invoice_number = models.CharField(max_length=50)
    invoice_date = models.DateField()
    license_value = models.DecimalField(max_digits=12, decimal_places=2)
    rate = models.DecimalField(max_digits=10, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    remarks = models.TextField(blank=True, null=True)
