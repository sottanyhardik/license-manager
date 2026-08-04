from django.db.models import Q
import pytest

from apps.core.models import HeadSIONNormsModel, HSCodeModel, ItemNameModel, SionNormClassModel
from apps.license.models import LicenseDetailsModel, LicenseImportItemsModel
from apps.license.signals import suspend_license_flag_recalc
from apps.license.utils.item_matcher import (
    bulk_auto_link_license_items,
    classify_packaging_item,
    extract_gsm_range,
    match_import_item_to_items,
    SUPPORTED_PACKAGING_NORMS,
)


@pytest.fixture
def e_norms():
    head_norm = HeadSIONNormsModel.objects.create(name="E Norms")
    return {
        code: SionNormClassModel.objects.create(head_norm=head_norm, norm_class=code)
        for code in ("E1", "E5")
    }


@pytest.fixture
def e132_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="E132 Norms")
    return SionNormClassModel.objects.create(head_norm=head_norm, norm_class="E132")


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


@pytest.mark.django_db
def test_aluminium_foil_text_alone_no_longer_matches_without_hsn_7607(e_norms):
    # Business rule: HSN 7607 is the only authority for ALUMINIUM FOIL —
    # the literal description text must not drive a match on its own.
    # Uses the REAL get_item_filters() (not monkeypatched).
    ItemNameModel.objects.create(name="ALUMINIUM FOIL - E1", sion_norm_class=e_norms["E1"])
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-ALFOIL-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Aluminium Foil wrap, decorative",
    )

    matched = match_import_item_to_items(import_item, ["E1"])

    assert not matched.exists()


@pytest.mark.django_db
def test_aluminium_foil_matches_via_hsn_7607(e_norms):
    expected = ItemNameModel.objects.create(name="ALUMINIUM FOIL - E1", sion_norm_class=e_norms["E1"])
    hs_code = HSCodeModel.objects.create(hs_code="76072090")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-ALFOIL-002")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        hs_code=hs_code,
        description="Decorative wrap",
    )

    matched = match_import_item_to_items(import_item, ["E1"])

    assert list(matched) == [expected]


@pytest.mark.django_db
def test_aluminium_foil_matches_via_description_containing_7607(e_norms):
    expected = ItemNameModel.objects.create(name="ALUMINIUM FOIL - E1", sion_norm_class=e_norms["E1"])
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-ALFOIL-003")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj,
        serial_number=1,
        description="Relevant Aluminium Foil HSN 7607",
    )

    matched = match_import_item_to_items(import_item, ["E1"])

    assert list(matched) == [expected]


# ─── E132 Auto Planning business rules — item detection ────────────────────
# These mirror the classification rules in services/e132_plan.py so item-name
# linking stays consistent with the planner. Each E132 entry is deliberately
# a SEPARATE, norm-scoped filter config (not merged into the shared E1/E5/E126
# entries) so tightening these never changes E1/E5/E126 item-name linking —
# see item_matcher.py's NUTS/CHEESE/RBD PALMOLEIN OIL entries.


@pytest.mark.django_db
def test_e132_nuts_requires_0802_and_word_boundary(e132_norm):
    expected = ItemNameModel.objects.create(name="NUTS - E132", sion_norm_class=e132_norm)
    hs_code = HSCodeModel.objects.create(hs_code="08021100")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-NUTS-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="Cashew Nuts",
    )

    matched = match_import_item_to_items(import_item, ["E132"])

    assert list(matched) == [expected]


@pytest.mark.django_db
def test_e132_nuts_word_boundary_excludes_peanut(e132_norm):
    ItemNameModel.objects.create(name="NUTS - E132", sion_norm_class=e132_norm)
    hs_code = HSCodeModel.objects.create(hs_code="08029090")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-NUTS-002")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="Peanut Kernels",
    )

    matched = match_import_item_to_items(import_item, ["E132"])

    assert not matched.exists()


@pytest.mark.django_db
def test_e132_cheese_requires_dairy_code_and_vegetable_and_oil(e132_norm):
    expected = ItemNameModel.objects.create(name="CHEESE - E132", sion_norm_class=e132_norm)
    hs_code = HSCodeModel.objects.create(hs_code="04061000")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-CHEESE-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code,
        description="Relevant Vegetable Oil Fat Blend",
    )

    matched = match_import_item_to_items(import_item, ["E132"])

    assert list(matched) == [expected]


@pytest.mark.django_db
def test_e132_cheese_dairy_code_alone_does_not_match(e132_norm):
    # Business rule: bare 0406 (no "vegetable"/"oil") no longer matches
    # CHEESE for E132 — unlike the loose E1/E5 CHEESE rule.
    ItemNameModel.objects.create(name="CHEESE - E132", sion_norm_class=e132_norm)
    hs_code = HSCodeModel.objects.create(hs_code="04061000")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-CHEESE-002")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="Fresh Cheese Only",
    )

    matched = match_import_item_to_items(import_item, ["E132"])

    assert not matched.exists()


@pytest.mark.django_db
def test_e132_cheese_strict_rule_does_not_affect_e1_e5(e_norms):
    # The loose E1/E5 CHEESE rule (bare 0406) must still match — confirms the
    # E132 tightening was scoped to its own filter entry only.
    expected = ItemNameModel.objects.create(name="CHEESE - E1", sion_norm_class=e_norms["E1"])
    hs_code = HSCodeModel.objects.create(hs_code="04061000")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-CHEESE-003")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="Fresh Cheese Only",
    )

    matched = match_import_item_to_items(import_item, ["E1"])

    assert list(matched) == [expected]


@pytest.mark.django_db
def test_e132_rbd_palmolein_oil_matches_via_hsn_1510(e132_norm):
    expected = ItemNameModel.objects.create(name="RBD PALMOLEIN OIL - E132", sion_norm_class=e132_norm)
    hs_code = HSCodeModel.objects.create(hs_code="15100000")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-RBD-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="RBD Palm Oil",
    )

    matched = match_import_item_to_items(import_item, ["E132"])

    assert list(matched) == [expected]


@pytest.mark.django_db
def test_e132_rbd_palmolein_oil_free_text_alone_does_not_match(e132_norm):
    # Business rule: E132's RBD detection is HSN 1510 (or "1510" in the
    # description) only — the old free-text "rbd palmolein oil" fallback
    # (still used by E1/E5/E126) does not apply here.
    ItemNameModel.objects.create(name="RBD PALMOLEIN OIL - E132", sion_norm_class=e132_norm)
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-RBD-002")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, description="RBD Palmolein Oil",
    )

    matched = match_import_item_to_items(import_item, ["E132"])

    assert not matched.exists()


@pytest.mark.django_db
def test_e132_palm_kernel_oil_matches_via_hsn_1513(e132_norm):
    expected = ItemNameModel.objects.create(name="PALM KERNEL OIL - E132", sion_norm_class=e132_norm)
    hs_code = HSCodeModel.objects.create(hs_code="15132900")
    license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-LIC-E132-PKO-001")
    import_item = LicenseImportItemsModel.objects.create(
        license=license_obj, serial_number=1, hs_code=hs_code, description="Palm Kernel Oil",
    )

    matched = match_import_item_to_items(import_item, ["E132"])

    assert list(matched) == [expected]


# ─── Packaging pre-classification (all norms) ──────────────────────────────


class TestClassifyPackagingItem:
    def test_hsn_3902_is_pp(self):
        assert classify_packaging_item('39023000', 'Polymer granules') == ('PP', 'RULE_PP')

    def test_hsn_3901_is_hdpe_regardless_of_description(self):
        assert classify_packaging_item('39011010', 'Plain packing film') == ('HDPE', 'RULE_HDPE')

    def test_description_keyword_hdpe_without_hsn(self):
        assert classify_packaging_item(None, 'HDPE granules') == ('HDPE', 'RULE_HDPE')

    def test_description_high_density_polyethylene_hyphenated(self):
        assert classify_packaging_item(None, 'High-Density Polyethylene sheet') == ('HDPE', 'RULE_HDPE')

    def test_description_keyword_ldpe(self):
        assert classify_packaging_item(None, 'LDPE film') == ('LDPE', 'RULE_LDPE')

    def test_description_low_density_polyethylene(self):
        assert classify_packaging_item(None, 'Low Density Polyethylene granules') == ('LDPE', 'RULE_LDPE')

    def test_description_keyword_lldpe_tags_distinctly_but_maps_to_ldpe(self):
        assert classify_packaging_item(None, 'LLDPE film') == ('LDPE', 'RULE_LLDPE')

    def test_description_linear_low_density_polyethylene(self):
        assert classify_packaging_item(None, 'Linear Low-Density Polyethylene resin') == ('LDPE', 'RULE_LLDPE')

    def test_paper_with_gsm_in_common_range(self):
        assert classify_packaging_item(None, 'Printing Paper 70 GSM') == ('PAPER', 'RULE_PAPER')

    def test_paper_with_gsm_range_upper_bound_is_used(self):
        assert classify_packaging_item(None, 'Coated Paper 40-100 GSM') == ('PAPER', 'RULE_PAPER')

    def test_paper_with_high_gsm_is_paper_board(self):
        assert classify_packaging_item(None, 'Duplex Paper 250 GSM') == ('PAPER BOARD', 'RULE_PAPER_BOARD')

    def test_paper_board_gsm_range_uses_max(self):
        assert classify_packaging_item(None, 'Paper 80/300 GSM') == ('PAPER BOARD', 'RULE_PAPER_BOARD')

    def test_paper_below_minimum_gsm_does_not_match(self):
        assert classify_packaging_item(None, 'Tissue Paper 20 GSM') is None

    def test_paper_without_gsm_does_not_match(self):
        assert classify_packaging_item(None, 'Assorted Paper products') is None

    def test_no_rule_matches_returns_none(self):
        assert classify_packaging_item('84213900', 'Filter cartridge') is None

    def test_pp_hsn_takes_priority_over_hdpe_hsn(self):
        # 3902 and 3901 are mutually exclusive prefixes, but this pins the
        # documented waterfall order (PP checked before HDPE).
        assert classify_packaging_item('39023000', 'HDPE blended masterbatch')[0] == 'PP'

    def test_hsn_7607_is_never_classified_as_packaging(self):
        # HSN 7607 (Aluminium Foil) is authoritative and exclusive — even
        # when the description also contains an HDPE/LDPE/PAPER keyword,
        # this must return None so ALUMINIUM FOIL (in get_item_filters())
        # is the only rule that ever claims it.
        assert classify_packaging_item('76071190', 'HDPE laminated aluminium foil') is None

    def test_description_containing_7607_is_never_classified_as_packaging(self):
        assert classify_packaging_item(None, 'Aluminium foil 7607 LDPE coated') is None

    def test_7607_guard_takes_priority_over_every_other_rule(self):
        # Even an unambiguous PP HSN must be overridden by a 7607 mention
        # in the description — 7607 wins regardless of where it appears.
        assert classify_packaging_item('39021000', 'Foil 7607 grade') is None


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
def make_norm():
    head_norm = HeadSIONNormsModel.objects.create(name="Packaging Test Norms")

    def _make(code):
        return SionNormClassModel.objects.create(head_norm=head_norm, norm_class=code)

    return _make


@pytest.mark.django_db
class TestMatchImportItemToItemsPackaging:
    @pytest.mark.parametrize('norm_code,description,expected_name', [
        ('E1', '39021000 Polypropylene Resin', 'PP - E1'),
        ('E5', 'HDPE Film Resin', 'HDPE - E5'),
        ('E126', 'LDPE Resin', 'LDPE - E126'),
        ('E132', 'Printing Paper 80 GSM', 'PAPER - E132'),
        ('COMMON', 'Duplex Paper Board 230 GSM', 'PAPER BOARD - COMMON'),
    ])
    def test_packaging_rule_resolves_to_licence_norm(
        self, make_norm, norm_code, description, expected_name,
    ):
        make_norm(norm_code)
        hs_code = HSCodeModel.objects.create(hs_code="39021000") if norm_code == 'E1' else None
        license_obj = LicenseDetailsModel.objects.create(license_number=f"MATCH-PKG-{norm_code}")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            hs_code=hs_code,
            description=description,
        )

        matched = match_import_item_to_items(import_item, [norm_code])

        assert list(matched.values_list("name", flat=True)) == [expected_name]
        assert ItemNameModel.objects.filter(name=expected_name).count() == 1

    def test_reuses_existing_item_name_case_insensitively(self, make_norm):
        e1_norm = make_norm('E1')
        existing = ItemNameModel.objects.create(name="hdpe - e1", sion_norm_class=e1_norm)
        license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-PKG-REUSE")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE packing material",
        )

        matched = match_import_item_to_items(import_item, ["E1"])

        assert list(matched) == [existing]
        assert ItemNameModel.objects.filter(name__iexact="hdpe - e1").count() == 1

    def test_no_rule_match_falls_back_to_generic_matcher(self, monkeypatch, make_norm):
        e1_norm = make_norm('E1')
        monkeypatch.setattr(
            "apps.license.utils.item_matcher.get_item_filters",
            lambda: [
                {
                    "base_name": "FALLBACK ITEM",
                    "norms": ["E1"],
                    "filters": [Q(description__icontains="fallback")],
                }
            ],
        )
        expected = ItemNameModel.objects.create(name="FALLBACK ITEM - E1", sion_norm_class=e1_norm)
        license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-PKG-FALLBACK")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="Fallback packaging item",
        )

        matched = match_import_item_to_items(import_item, ["E1"])

        assert list(matched) == [expected]

    def test_uses_first_supported_norm_class_when_licence_has_several(self, make_norm):
        make_norm('E1')
        make_norm('E5')
        license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-PKG-MULTI")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE granules",
        )

        matched = match_import_item_to_items(import_item, ["E1", "E5"])

        assert list(matched.values_list("name", flat=True)) == ["HDPE - E1"]

    def test_skips_an_unsupported_norm_ahead_of_a_supported_one(self, monkeypatch, make_norm):
        # 'A3627' isn't in SUPPORTED_PACKAGING_NORMS — even though it's
        # listed FIRST, the deterministic resolver must skip past it to the
        # supported 'E1', never blindly take license_norm_classes[0].
        assert 'A3627' not in SUPPORTED_PACKAGING_NORMS
        make_norm('E1')
        monkeypatch.setattr(
            "apps.license.utils.item_matcher.get_item_filters", lambda: [],
        )
        license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-PKG-SKIP")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE granules",
        )

        matched = match_import_item_to_items(import_item, ["A3627", "E1"])

        assert list(matched.values_list("name", flat=True)) == ["HDPE - E1"]

    def test_unsupported_norm_never_triggers_packaging_classification(self, monkeypatch):
        # No SUPPORTED_PACKAGING_NORMS norm present at all -> packaging
        # engine must not fire, and must not auto-create an ItemNameModel,
        # even though the description would otherwise match the HDPE rule.
        assert 'A3627' not in SUPPORTED_PACKAGING_NORMS
        monkeypatch.setattr(
            "apps.license.utils.item_matcher.get_item_filters", lambda: [],
        )
        license_obj = LicenseDetailsModel.objects.create(license_number="MATCH-PKG-UNSUPPORTED")
        import_item = LicenseImportItemsModel.objects.create(
            license=license_obj,
            serial_number=1,
            description="HDPE granules",
        )

        matched = match_import_item_to_items(import_item, ["A3627"])

        assert not matched.exists()
        assert not ItemNameModel.objects.filter(name__icontains="HDPE").exists()


@pytest.mark.django_db
class TestBulkAutoLinkLicenseItemsPackaging:
    def test_packaging_items_linked_via_licence_norm_and_excluded_from_generic_pass(
        self, monkeypatch, make_norm,
    ):
        e1_norm = make_norm('E1')
        generic_calls = []

        def _tracking_filters():
            generic_calls.append(True)
            return []

        monkeypatch.setattr(
            "apps.license.utils.item_matcher.get_item_filters", _tracking_filters,
        )

        license_obj = LicenseDetailsModel.objects.create(license_number="BULK-PKG-001")
        license_obj.export_license.create(norm_class=e1_norm)
        with suspend_license_flag_recalc():
            pkg_item = LicenseImportItemsModel.objects.create(
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
        pkg_item.refresh_from_db()
        unrelated_item.refresh_from_db()
        assert list(pkg_item.items.values_list("name", flat=True)) == ["LDPE - E1"]
        assert not unrelated_item.items.exists()

    def test_bulk_link_resolves_paper_board_for_common_norm(self, make_norm):
        common_norm = make_norm('COMMON')
        license_obj = LicenseDetailsModel.objects.create(license_number="BULK-PKG-002")
        license_obj.export_license.create(norm_class=common_norm)
        with suspend_license_flag_recalc():
            item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=1,
                description="Duplex Paper Board 230 GSM",
            )

        linked_count = bulk_auto_link_license_items(license_obj)

        assert linked_count == 1
        item.refresh_from_db()
        assert list(item.items.values_list("name", flat=True)) == ["PAPER BOARD - COMMON"]

    def test_bulk_link_skips_an_unsupported_norm_ahead_of_a_supported_one(self, make_norm):
        assert 'A3627' not in SUPPORTED_PACKAGING_NORMS
        a3627_norm = make_norm('A3627')
        e1_norm = make_norm('E1')
        license_obj = LicenseDetailsModel.objects.create(license_number="BULK-PKG-003")
        # Order matters here: A3627 is created first, so norm_classes[0]
        # would have been 'A3627' under the old (unsafe) resolution.
        license_obj.export_license.create(norm_class=a3627_norm)
        license_obj.export_license.create(norm_class=e1_norm)
        with suspend_license_flag_recalc():
            item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=1,
                description="HDPE granules",
            )

        linked_count = bulk_auto_link_license_items(license_obj)

        assert linked_count == 1
        item.refresh_from_db()
        assert list(item.items.values_list("name", flat=True)) == ["HDPE - E1"]

    def test_bulk_link_never_creates_packaging_names_for_an_unsupported_norm(self, make_norm):
        assert 'A3627' not in SUPPORTED_PACKAGING_NORMS
        a3627_norm = make_norm('A3627')
        license_obj = LicenseDetailsModel.objects.create(license_number="BULK-PKG-004")
        license_obj.export_license.create(norm_class=a3627_norm)
        with suspend_license_flag_recalc():
            item = LicenseImportItemsModel.objects.create(
                license=license_obj,
                serial_number=1,
                description="HDPE granules",
            )

        linked_count = bulk_auto_link_license_items(license_obj)

        assert linked_count == 0
        item.refresh_from_db()
        assert not item.items.exists()
        assert not ItemNameModel.objects.filter(name__icontains="HDPE").exists()
