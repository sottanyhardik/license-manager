from django.db.models import Q
import pytest

from apps.core.models import HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.signals import suspend_license_flag_recalc
from apps.license.utils.item_matcher import (
    bulk_auto_link_license_items,
    classify_pp_norm_item,
    extract_gsm_range,
    match_import_item_to_items,
)


@pytest.fixture
def e_norms():
    head_norm = HeadSIONNormsModel.objects.create(name="E Norms")
    return {
        code: SionNormClassModel.objects.create(head_norm=head_norm, norm_class=code)
        for code in ("E1", "E5")
    }


@pytest.mark.django_db
def test_match_import_item_uses_applicable_norm_for_multi_norm_license(monkeypatch, e_norms):
    monkeypatch.setattr(
        "apps.license.utils.item_matcher.get_item_filters",
        lambda: [
            {
                "base_name": "DIETARY FIBRE",
                "norms": ["E5"],
                "filters": [Q(description__icontains="fibre")],
            }
        ],
    )
    expected = ItemNameModel.objects.create(
        name="DIETARY FIBRE - E5",
        sion_norm_class=e_norms["E5"],
    )
    ItemNameModel.objects.create(
        name="DIETARY FIBRE - E1",
        sion_norm_class=e_norms["E1"],
    )
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Dietary fibre blend",
    )

    matched = match_import_item_to_items(import_item, ["E1", "E5"])

    assert list(matched) == [expected]


@pytest.mark.django_db
def test_match_import_item_returns_empty_queryset_without_norms(monkeypatch):
    monkeypatch.setattr(
        "apps.license.utils.item_matcher.get_item_filters",
        lambda: [
            {
                "base_name": "SUGAR",
                "norms": ["E1"],
                "filters": [Q(description__icontains="sugar")],
            }
        ],
    )
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-002")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Sugar",
    )

    matched = match_import_item_to_items(import_item, [])

    assert not matched.exists()


# ─── PP-norm packaging pre-classification ──────────────────────────────────


class TestClassifyPpNormItem:
    def test_hsn_3902_is_pp(self):
        assert classify_pp_norm_item('39023000', 'Polymer granules') == (
            'PP - COMMON', 'PP_RULE_PP_COMMON',
        )

    def test_hsn_3901_is_hdpe_regardless_of_description(self):
        assert classify_pp_norm_item('39011010', 'Plain packing film') == (
            'HDPE - COMMON', 'PP_RULE_HDPE_COMMON',
        )

    def test_description_keyword_hdpe_without_hsn(self):
        assert classify_pp_norm_item(None, 'HDPE granules') == (
            'HDPE - COMMON', 'PP_RULE_HDPE_COMMON',
        )

    def test_description_high_density_polyethylene_hyphenated(self):
        assert classify_pp_norm_item(None, 'High-Density Polyethylene sheet') == (
            'HDPE - COMMON', 'PP_RULE_HDPE_COMMON',
        )

    def test_description_keyword_ldpe(self):
        assert classify_pp_norm_item(None, 'LDPE film') == (
            'LDPE - COMMON', 'PP_RULE_LDPE_COMMON',
        )

    def test_description_low_density_polyethylene(self):
        assert classify_pp_norm_item(None, 'Low Density Polyethylene granules') == (
            'LDPE - COMMON', 'PP_RULE_LDPE_COMMON',
        )

    def test_description_keyword_lldpe_tags_distinctly_but_maps_to_ldpe(self):
        assert classify_pp_norm_item(None, 'LLDPE film') == (
            'LDPE - COMMON', 'PP_RULE_LLDPE_COMMON',
        )

    def test_description_linear_low_density_polyethylene(self):
        assert classify_pp_norm_item(None, 'Linear Low-Density Polyethylene resin') == (
            'LDPE - COMMON', 'PP_RULE_LLDPE_COMMON',
        )

    def test_paper_with_gsm_in_common_range(self):
        assert classify_pp_norm_item(None, 'Printing Paper 70 GSM') == (
            'PAPER - COMMON', 'PP_RULE_PAPER_COMMON',
        )

    def test_paper_with_gsm_range_upper_bound_is_used(self):
        assert classify_pp_norm_item(None, 'Coated Paper 40-100 GSM') == (
            'PAPER - COMMON', 'PP_RULE_PAPER_COMMON',
        )

    def test_paper_with_high_gsm_is_paper_board(self):
        assert classify_pp_norm_item(None, 'Duplex Paper 250 GSM') == (
            'PAPER BOARD - COMMON', 'PP_RULE_PAPER_BOARD_COMMON',
        )

    def test_paper_board_gsm_range_uses_max(self):
        assert classify_pp_norm_item(None, 'Paper 80/300 GSM') == (
            'PAPER BOARD - COMMON', 'PP_RULE_PAPER_BOARD_COMMON',
        )

    def test_paper_below_minimum_gsm_does_not_match(self):
        assert classify_pp_norm_item(None, 'Tissue Paper 20 GSM') is None

    def test_paper_without_gsm_does_not_match(self):
        assert classify_pp_norm_item(None, 'Assorted Paper products') is None

    def test_no_rule_matches_returns_none(self):
        assert classify_pp_norm_item('84213900', 'Filter cartridge') is None

    def test_pp_hsn_takes_priority_over_hdpe_hsn(self):
        # 3902 and 3901 are mutually exclusive prefixes, but this pins the
        # documented waterfall order (PP checked before HDPE).
        assert classify_pp_norm_item('39023000', 'HDPE blended masterbatch')[0] == 'PP - COMMON'


class TestExtractGsmRange:
    @pytest.mark.parametrize('text,expected', [
        ('70 GSM', (70, 70)),
        ('70GSM', (70, 70)),
        ('70 G.S.M.', (70, 70)),
        ('40-100 GSM', (40, 100)),
        ('40 TO 100 GSM', (40, 100)),
        ('40/100 GSM', (40, 100)),
        ('40~100 GSM', (40, 100)),
        ('180 GSM', (180, 180)),
        ('Coated Paper 90 GSM White', (90, 90)),
        ('No gsm mentioned here', None),
        (None, None),
        ('', None),
    ])
    def test_extract(self, text, expected):
        assert extract_gsm_range(text) == expected


@pytest.fixture
def pp_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="PP Norms")
    return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="PP")


@pytest.mark.django_db
class TestMatchImportItemToItemsPpNorm:
    def test_pp_norm_hsn_3902_creates_and_returns_pp_common(self, pp_norm):
        hs_code = HSCodeModel.objects.create(hs_code="39023000")
        license_obj = LicenseDetailsModel.objects.create(license_number="PP-LIC-001")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            hs_code=hs_code,
            description="Polypropylene granules",
        )

        matched = match_import_item_to_items(import_item, ["PP"])

        assert list(matched.values_list("name", flat=True)) == ["PP - COMMON"]
        assert ItemNameModel.objects.filter(name="PP - COMMON").count() == 1

    def test_pp_norm_reuses_existing_item_name_case_insensitively(self, pp_norm):
        existing = ItemNameModel.objects.create(name="hdpe - common", sion_norm_class=pp_norm)
        license_obj = LicenseDetailsModel.objects.create(license_number="PP-LIC-002")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE packing material",
        )

        matched = match_import_item_to_items(import_item, ["PP"])

        assert list(matched) == [existing]
        assert ItemNameModel.objects.filter(name__iexact="hdpe - common").count() == 1

    def test_pp_norm_no_rule_match_falls_back_to_generic_matcher(self, monkeypatch, pp_norm):
        monkeypatch.setattr(
            "apps.license.utils.item_matcher.get_item_filters",
            lambda: [
                {
                    "base_name": "FALLBACK ITEM",
                    "norms": ["PP"],
                    "filters": [Q(description__icontains="fallback")],
                }
            ],
        )
        expected = ItemNameModel.objects.create(name="FALLBACK ITEM - PP", sion_norm_class=pp_norm)
        license_obj = LicenseDetailsModel.objects.create(license_number="PP-LIC-003")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Fallback packaging item",
        )

        matched = match_import_item_to_items(import_item, ["PP"])

        assert list(matched) == [expected]

    def test_non_pp_norm_is_unaffected_by_pp_rules(self, monkeypatch, e_norms):
        # A description that WOULD match the PP rules must be ignored
        # entirely when 'PP' is not among the licence's norm classes.
        monkeypatch.setattr(
            "apps.license.utils.item_matcher.get_item_filters",
            lambda: [
                {
                    "base_name": "DIETARY FIBRE",
                    "norms": ["E5"],
                    "filters": [Q(description__icontains="fibre")],
                }
            ],
        )
        license_obj = LicenseDetailsModel.objects.create(license_number="PP-LIC-004")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE packaging film",
        )

        matched = match_import_item_to_items(import_item, ["E1", "E5"])

        assert not matched.exists()
        assert not ItemNameModel.objects.filter(name="HDPE - COMMON").exists()


@pytest.mark.django_db
class TestBulkAutoLinkLicenseItemsPpNorm:
    def test_pp_norm_items_linked_via_new_rules_and_excluded_from_generic_pass(
        self, monkeypatch, pp_norm,
    ):
        generic_calls = []

        def _tracking_filters():
            generic_calls.append(True)
            return []

        monkeypatch.setattr(
            "apps.license.utils.item_matcher.get_item_filters", _tracking_filters,
        )

        license_obj = LicenseDetailsModel.objects.create(license_number="PP-LIC-BULK-001")
        license_obj.export_license.create(norm_class=pp_norm)
        with suspend_license_flag_recalc():
            pp_item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=1,
                description="LLDPE film roll",
            )
            unrelated_item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=2,
                description="Unrelated component",
            )

        linked_count = bulk_auto_link_license_items(license_obj)

        assert linked_count == 1
        pp_item.refresh_from_db()
        unrelated_item.refresh_from_db()
        assert list(pp_item.items.values_list("name", flat=True)) == ["LDPE - COMMON"]
        assert not unrelated_item.items.exists()
