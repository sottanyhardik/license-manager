"""The shipped reference mapping must be complete and valid."""

import unittest

from mds_client.model_map import DEFAULT_MDS_MODELS, KEYLESS_MODEL_LABELS

REQUIRED_KEYS = {"endpoint", "natural_key", "mirror_model", "mds_model_label"}
EXPECTED_LABELS = {
    "core.CompanyModel", "core.PortModel", "core.ItemHeadModel", "core.ItemGroupModel",
    "core.ItemNameModel", "core.HSCodeModel", "core.HeadSIONNormsModel",
    "core.SionNormClassModel", "core.SIONExportModel", "core.SIONImportModel",
    "core.SionNormNote", "core.SionNormCondition", "core.ProductDescriptionModel",
    "core.UnitPriceModel", "core.SchemeCode", "core.NotificationNumber",
    "core.ExchangeRateModel",
}


class DefaultMdsModelsTests(unittest.TestCase):
    def test_covers_all_17_masters(self):
        self.assertEqual(set(DEFAULT_MDS_MODELS), EXPECTED_LABELS)
        self.assertEqual(len(DEFAULT_MDS_MODELS), 17)

    def test_every_entry_has_required_keys(self):
        for label, cfg in DEFAULT_MDS_MODELS.items():
            self.assertTrue(REQUIRED_KEYS <= set(cfg), f"{label} missing keys")
            for key in REQUIRED_KEYS:
                self.assertTrue(cfg[key], f"{label}.{key} is empty")

    def test_endpoints_are_unique(self):
        endpoints = [c["endpoint"] for c in DEFAULT_MDS_MODELS.values()]
        self.assertEqual(len(endpoints), len(set(endpoints)))

    def test_keyless_labels_match_uid_entries(self):
        expected = {l for l, c in DEFAULT_MDS_MODELS.items() if c["natural_key"] == "uid"}
        self.assertEqual(set(KEYLESS_MODEL_LABELS), expected)
        # the 7 keyless masters per ADR Decision 6
        self.assertEqual(len(KEYLESS_MODEL_LABELS), 7)

    def test_passes_settings_validation_shape(self):
        # mirror the mds_client.settings.get_models() required-key check
        from mds_client.settings import REQUIRED_MODEL_KEYS
        for label, cfg in DEFAULT_MDS_MODELS.items():
            missing = [k for k in REQUIRED_MODEL_KEYS if not cfg.get(k)]
            self.assertEqual(missing, [], f"{label} fails settings validation: {missing}")


if __name__ == "__main__":
    unittest.main()
