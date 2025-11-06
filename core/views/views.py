# core/views.py
from .mater_view import MasterViewSet
from ..models import CompanyModel, PortModel, HSCodeModel, HeadSIONNormsModel, SionNormClassModel, SIONExportModel, \
    SIONImportModel, HSCodeDutyModel, ProductDescriptionModel, UnitPriceModel
from ..serializers import CompanySerializer, PortSerializer, HSCodeSerializer, HeadSIONNormsSerializer, \
    SionNormClassNestedSerializer, SIONExportSerializer, SIONImportSerializer, HSCodeDutySerializer, \
    ProductDescriptionSerializer, UnitPriceSerializer

# Auto-generated viewsets (1 line each)

CompanyViewSet = MasterViewSet.create(
    CompanyModel,
    CompanySerializer,
    config={
        "search": ["iec", "name"],
        "filter": ["iec", "gst_number"],
        "list_display": ["iec", "name", "gst_number"],
        "form_fields": ["iec", "name", "gst_number", "email"],
    }

)

# Port
PortViewSet = MasterViewSet.create(
    PortModel,
    PortSerializer,
    config={
        "search": ["code", "name"],
        "filter": [],
        "list_display": ["code", "name"],
        "form_fields": ["code", "name"],
    },
)

HSCodeViewSet = MasterViewSet.create(
    HSCodeModel,
    HSCodeSerializer,
    config={
        "search": ["hs_code", "product_description"],
        "filter": [],
        "list_display": ["hs_code", "product_description", "unit_price", "unit"],
        "form_fields": ["hs_code", "product_description", "unit_price", "basic_duty", "unit", "policy"],
    },
)

HeadSIONNormsViewSet = MasterViewSet.create(
    HeadSIONNormsModel,
    HeadSIONNormsSerializer,
    config={
        "search": ["name"],
        "list_display": ["id", "name"],
        "form_fields": ["name"],
    },
)

SionNormClassViewSet = MasterViewSet.create(
    SionNormClassModel,
    SionNormClassNestedSerializer,
    config={
        "search": ["norm_class", "description"],
        "filter": [],
        "list_display": ["norm_class", "description", "head_norm_name"],
        "form_fields": ["norm_class", "description", "head_norm"],
    },
)

HSCodeDutyViewSet = MasterViewSet.create(HSCodeDutyModel, HSCodeDutySerializer, ["hs_code"])
ProductDescriptionViewSet = MasterViewSet.create(ProductDescriptionModel, ProductDescriptionSerializer, ["product_description"])
UnitPriceViewSet = MasterViewSet.create(UnitPriceModel, UnitPriceSerializer, ["name", "label"])
