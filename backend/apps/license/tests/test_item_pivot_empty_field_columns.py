from apps.license.views.item_pivot_report import _pivot_has_value, _pivot_item_fields


def _group(licenses_items, total_items, key="FRUIT"):
    return {
        "totals": {"items": {key: total_items}},
        "licenses": [{"items": {key: items}} for items in licenses_items],
    }


def _keys(item, group):
    return [key for key, _label in _pivot_item_fields(item, group)]


def test_has_value_treats_null_empty_and_zero_as_empty():
    assert _pivot_has_value(None) is False
    assert _pivot_has_value("") is False
    assert _pivot_has_value(0) is False
    assert _pivot_has_value("0.000") is False
    assert _pivot_has_value(0.5) is True
    assert _pivot_has_value("abc") is True


def test_hsn_and_description_always_show_even_when_empty():
    item = {"key": "FRUIT", "product_category": "FRUIT"}

    assert _keys(item, _group([{}], {})) == ["hsn_code", "description"]


def test_restriction_and_billed_columns_drop_when_empty_or_zero_everywhere():
    item = {"key": "FRUIT", "product_category": "FRUIT"}
    group = _group([{"billed_qty": 0, "billed_cif": 0, "restriction_percent": None, "total_qty": 5}],
                   {"billed_qty": 0, "billed_cif": 0, "total_qty": 5})

    keys = _keys(item, group)
    assert "billed_qty" not in keys
    assert "billed_cif" not in keys
    assert "restriction_percent" not in keys
    assert "restriction_value" not in keys
    assert "total_qty" in keys


def test_column_stays_when_only_one_licence_or_only_the_total_has_a_value():
    item = {"key": "FRUIT", "product_category": "FRUIT"}

    assert "billed_qty" in _keys(item, _group([{"billed_qty": 0}, {"billed_qty": 2}], {"billed_qty": 2}))
    assert "billed_qty" in _keys(item, _group([{"billed_qty": 0}], {"billed_qty": 2}))


def test_rutile_unit_price_column_only_when_it_has_a_value():
    rutile = {"key": "RUTILE", "product_category": "RUTILE"}
    with_price = _group([{"unit_price": 2.5}], {}, key="RUTILE")
    without_price = _group([{"unit_price": None}], {}, key="RUTILE")

    with_labels = [label for _key, label in _pivot_item_fields(rutile, with_price)]
    without_labels = [label for _key, label in _pivot_item_fields(rutile, without_price)]

    assert "UNIT PRICE" in with_labels
    assert "UNIT PRICE" not in without_labels
