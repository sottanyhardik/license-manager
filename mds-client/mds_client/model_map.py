"""
Reference ``MDS_MODELS`` mapping for the License Manager consumer — all 17
masters served by the Master-Data Service.

A consuming project can adopt it wholesale::

    from mds_client.model_map import DEFAULT_MDS_MODELS
    MDS_MODELS = DEFAULT_MDS_MODELS

...or copy/trim it. Each entry maps the consumer's local model_label to:
- ``endpoint``        : the MDS URL segment (router basename path)
- ``natural_key``     : the field shared by MDS + the local mirror row
- ``mirror_model``    : "app_label.ModelName" of the LOCAL mirror model to upsert
- ``mds_model_label`` : the label MDS stamps on its change feed (for delete apply)

NOTE on the keyless masters (natural_key = "uid"): MDS assigns each of these a
synthetic ``uid`` UUID (ADR-001 Decision 6). To sync them, the LOCAL mirror model
must also carry a matching ``uid`` column — added during mirror hydration
(ADR Phase 5). Until then, sync only the business-keyed masters.
"""

DEFAULT_MDS_MODELS = {
    # --- business-keyed masters (ready to sync as-is) ----------------------
    "core.CompanyModel": {
        "endpoint": "companies",
        "natural_key": "iec",
        "mirror_model": "core.CompanyModel",
        "mds_model_label": "masters.Company",
    },
    "core.PortModel": {
        "endpoint": "ports",
        "natural_key": "code",
        "mirror_model": "core.PortModel",
        "mds_model_label": "masters.Port",
    },
    "core.ItemHeadModel": {
        "endpoint": "item-heads",
        "natural_key": "name",
        "mirror_model": "core.ItemHeadModel",
        "mds_model_label": "masters.ItemHead",
    },
    "core.ItemGroupModel": {
        "endpoint": "item-groups",
        "natural_key": "name",
        "mirror_model": "core.ItemGroupModel",
        "mds_model_label": "masters.ItemGroup",
    },
    "core.ItemNameModel": {
        "endpoint": "item-names",
        "natural_key": "name",
        "mirror_model": "core.ItemNameModel",
        "mds_model_label": "masters.ItemName",
    },
    "core.HSCodeModel": {
        "endpoint": "hs-codes",
        "natural_key": "hs_code",
        "mirror_model": "core.HSCodeModel",
        "mds_model_label": "masters.HSCode",
    },
    "core.SionNormClassModel": {
        "endpoint": "sion-norm-classes",
        "natural_key": "norm_class",
        "mirror_model": "core.SionNormClassModel",
        "mds_model_label": "masters.SIONNormClass",
    },
    "core.SchemeCode": {
        "endpoint": "scheme-codes",
        "natural_key": "code",
        "mirror_model": "core.SchemeCode",
        "mds_model_label": "masters.SchemeCode",
    },
    "core.NotificationNumber": {
        "endpoint": "notification-numbers",
        "natural_key": "code",
        "mirror_model": "core.NotificationNumber",
        "mds_model_label": "masters.NotificationNumber",
    },
    "core.ExchangeRateModel": {
        "endpoint": "exchange-rates",
        "natural_key": "date",
        "mirror_model": "core.ExchangeRateModel",
        "mds_model_label": "masters.ExchangeRate",
    },
    # --- keyless masters (require a `uid` column on the local mirror) -------
    "core.HeadSIONNormsModel": {
        "endpoint": "head-sion-norms",
        "natural_key": "uid",
        "mirror_model": "core.HeadSIONNormsModel",
        "mds_model_label": "masters.HeadSIONNorm",
    },
    "core.SIONExportModel": {
        "endpoint": "sion-exports",
        "natural_key": "uid",
        "mirror_model": "core.SIONExportModel",
        "mds_model_label": "masters.SIONExport",
    },
    "core.SIONImportModel": {
        "endpoint": "sion-imports",
        "natural_key": "uid",
        "mirror_model": "core.SIONImportModel",
        "mds_model_label": "masters.SIONImport",
    },
    "core.SionNormNote": {
        "endpoint": "sion-norm-notes",
        "natural_key": "uid",
        "mirror_model": "core.SionNormNote",
        "mds_model_label": "masters.SIONNormNote",
    },
    "core.SionNormCondition": {
        "endpoint": "sion-norm-conditions",
        "natural_key": "uid",
        "mirror_model": "core.SionNormCondition",
        "mds_model_label": "masters.SIONNormCondition",
    },
    "core.ProductDescriptionModel": {
        "endpoint": "product-descriptions",
        "natural_key": "uid",
        "mirror_model": "core.ProductDescriptionModel",
        "mds_model_label": "masters.ProductDescription",
    },
    "core.UnitPriceModel": {
        "endpoint": "unit-prices",
        "natural_key": "uid",
        "mirror_model": "core.UnitPriceModel",
        "mds_model_label": "masters.UnitPrice",
    },
}

#: labels whose local mirror needs a synthetic `uid` column before syncing.
KEYLESS_MODEL_LABELS = tuple(
    label for label, cfg in DEFAULT_MDS_MODELS.items() if cfg["natural_key"] == "uid"
)
