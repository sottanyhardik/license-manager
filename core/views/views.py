# core/views.py
from .mater_view import MasterViewSet
from ..models import CompanyModel, PortModel, HSCodeModel, HeadSIONNormsModel, SionNormClassModel, SIONExportModel, \
    SIONImportModel, HSCodeDutyModel, ProductDescriptionModel, UnitPriceModel
from ..serializers import CompanySerializer, PortSerializer, HSCodeSerializer, HeadSIONNormsSerializer, \
    SionNormClassNestedSerializer, SIONExportSerializer, SIONImportSerializer, HSCodeDutySerializer, \
    ProductDescriptionSerializer, UnitPriceSerializer

# Auto-generated viewsets (1 line each)
CompanyViewSet = MasterViewSet.create(CompanyModel, CompanySerializer, ["iec", "name", "gst_number"])
PortViewSet = MasterViewSet.create(PortModel, PortSerializer, ["code", "name"])
HSCodeViewSet = MasterViewSet.create(HSCodeModel, HSCodeSerializer, ["hs_code", "product_description"])
HeadSIONNormsViewSet = MasterViewSet.create(HeadSIONNormsModel, HeadSIONNormsSerializer, ["name"])
SionNormClassViewSet = MasterViewSet.create(SionNormClassModel, SionNormClassNestedSerializer, ["norm_class", "description"])
SIONExportViewSet = MasterViewSet.create(SIONExportModel, SIONExportSerializer, ["description", "unit"])
SIONImportViewSet = MasterViewSet.create(SIONImportModel, SIONImportSerializer, ["description", "unit", "hsn_code__hs_code"])
HSCodeDutyViewSet = MasterViewSet.create(HSCodeDutyModel, HSCodeDutySerializer, ["hs_code"])
ProductDescriptionViewSet = MasterViewSet.create(ProductDescriptionModel, ProductDescriptionSerializer, ["product_description"])
UnitPriceViewSet = MasterViewSet.create(UnitPriceModel, UnitPriceSerializer, ["name", "label"])
