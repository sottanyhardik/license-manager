"""
Core serializer utilities for the license management system.
"""

from .mixins import (
    FormDataParserMixin,
    NestedObjectNormalizerMixin,
    EmptyStringNormalizerMixin,
    NestedValidationMixin,
    FormDataNestedMixin,
)

from .fields import (
    SafeDateField,
    SafeDateTimeField,
    FlexibleDateField,
    FinancialYearField,
    DateFormatterMixin,
)

# Import model serializers from models.py
from .models import (
    AuditSerializerMixin,
    CompanySerializer,
    PortSerializer,
    HSCodeSerializer,
    HeadSIONNormsSerializer,
    SIONExportSerializer,
    SIONImportSerializer,
    SionNormNoteSerializer,
    SionNormConditionSerializer,
    SionNormClassNestedSerializer,
    HSCodeDutySerializer,
    ProductDescriptionSerializer,
    UnitPriceSerializer,
    GroupSerializer,
    ItemHeadSerializer,
    ItemNameSerializer,
    TransferLetterSerializer,
    ExchangeRateSerializer,
    PurchaseStatusSerializer,
)

__all__ = [
    # Mixins
    'FormDataParserMixin',
    'NestedObjectNormalizerMixin',
    'EmptyStringNormalizerMixin',
    'NestedValidationMixin',
    'FormDataNestedMixin',
    # Fields
    'SafeDateField',
    'SafeDateTimeField',
    'FlexibleDateField',
    'FinancialYearField',
    'DateFormatterMixin',
    # Model Serializers
    'AuditSerializerMixin',
    'CompanySerializer',
    'PortSerializer',
    'HSCodeSerializer',
    'HeadSIONNormsSerializer',
    'SIONExportSerializer',
    'SIONImportSerializer',
    'SionNormNoteSerializer',
    'SionNormConditionSerializer',
    'SionNormClassNestedSerializer',
    'HSCodeDutySerializer',
    'ProductDescriptionSerializer',
    'UnitPriceSerializer',
    'GroupSerializer',
    'ItemHeadSerializer',
    'ItemNameSerializer',
    'TransferLetterSerializer',
    'ExchangeRateSerializer',
    'PurchaseStatusSerializer',
]
