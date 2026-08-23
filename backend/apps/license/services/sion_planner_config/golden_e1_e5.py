"""Immutable expected rows captured from the approved E1/E5 contracts.

These values are literals rather than values generated at test time.  They
therefore remain a useful shadow oracle after legacy implementations are
retired.  All numeric values remain strings until converted to Decimal by a
comparison runner.
"""

E1_GOLDEN_CASES = (
    {
        "name": "full waterfall with dynamic terminal egg rate",
        "balance_cif": "1200",
        "items": (
            ("conf", "OTHER CONFECTIONERY INGREDIENTS", "100"),
            ("cocoa", "COCOA MASS", "10"),
            ("milk", "MILK PRODUCTS", "100"),
            ("egg", "EGG ALBUMIN", "10"),
        ),
        "lines": (
            ("conf", "OTHER CONFECTIONERY INGREDIENTS", "OTHER CONFECTIONERY INGREDIENTS", "100", "3.0000", "300.0000"),
            ("cocoa", "COCOA MASS", "COCOA MASS", "10", "10.0000", "100.0000"),
            ("milk", "MILK PRODUCTS", "DWP", "100", "6.5000", "650.0000"),
            ("egg", "EGG ALBUMIN", "EGG ALBUMIN", "10", "15.0000", "150.0000"),
        ),
        "remaining_cif": "0.00",
    },
    {
        "name": "category shared rate preserves input rows",
        "balance_cif": "300",
        "items": (
            ("conf-a", "OTHER CONFECTIONERY INGREDIENTS", "100"),
            ("conf-b", "OTHER CONFECTIONERY INGREDIENTS", "50"),
            ("cocoa", "COCOA MASS", "20"),
        ),
        "lines": (
            ("conf-a", "OTHER CONFECTIONERY INGREDIENTS", "OTHER CONFECTIONERY INGREDIENTS", "100", "2.0000", "200.0000"),
            ("conf-b", "OTHER CONFECTIONERY INGREDIENTS", "OTHER CONFECTIONERY INGREDIENTS", "50", "2.0000", "100.0000"),
        ),
        "remaining_cif": "0",
    },
)

E5_GOLDEN_CASES = (
    {
        "name": "normal oils milk WPC and wheat mop-up",
        "balance_cif": "2000",
        "items": (
            ("fibre", "DIETARY FIBRE", "100"),
            ("pko", "PALM KERNEL OIL", "100"),
            ("milk", "MILK PRODUCTS", "100"),
            ("wpc", "EGG ALBUMIN / WPC", "10"),
            ("wheat", "WHEAT FLOUR", "100"),
        ),
        "options": {"min_plan_qty": "0", "floor_qty": False},
        "lines": (
            ("fibre", "DIETARY FIBRE", "DIETARY FIBRE", "100", "3.0000", "300.0000"),
            ("pko", "PALM KERNEL OIL", "PALM KERNEL OIL", "100", "1.8000", "180.0000"),
            ("milk", "MILK PRODUCTS", "DWP", "100", "6.5000", "650.0000"),
            ("wpc", "EGG ALBUMIN / WPC", "WPC", "10", "25.0000", "250.0000"),
            ("wheat", "WHEAT FLOUR", "WHEAT FLOUR", "100", "6.2000", "620.0000"),
        ),
        "remaining_cif": "0.00",
        "special_validation_triggered": False,
    },
    {
        "name": "special validation precedes oils and skips normal milk",
        "balance_cif": "1000",
        "items": (
            ("fibre", "DIETARY FIBRE", "100"),
            ("milk", "MILK PRODUCTS", "500"),
            ("wpc", "EGG ALBUMIN / WPC", "500"),
            ("pko", "PALM KERNEL OIL", "100"),
        ),
        "options": {"min_plan_qty": "0", "floor_qty": False},
        "lines": (
            ("fibre", "DIETARY FIBRE", "DIETARY FIBRE", "100", "3.0000", "300.0000"),
            ("milk", "MILK PRODUCTS", "SWP", "500", "1.4000", "700.0000"),
        ),
        "remaining_cif": "0.00",
        "special_validation_triggered": True,
    },
    {
        "name": "auto fixed rate floors quantity",
        "balance_cif": "17",
        "items": (("pko", "PALM KERNEL OIL", "100"),),
        "options": {"min_plan_qty": "0", "floor_qty": True},
        "lines": (("pko", "PALM KERNEL OIL", "PALM KERNEL OIL", "9", "1.8000", "16.2000"),),
        "remaining_cif": "0.80",
        "special_validation_triggered": False,
    },
)

