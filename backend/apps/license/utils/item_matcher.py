"""
Utility module for matching license import items to ItemNameModel items.
This ensures consistent item matching logic across the codebase.
"""
import logging
import re

from django.db.models import Q

logger = logging.getLogger(__name__)


def get_item_filters():
    """
    Returns the comprehensive filter definitions for matching import items to ItemNameModel items.
    This is the single source of truth for item classification logic.

    Returns:
        list: List of dictionaries containing base_name, norms, and filters for each item type
    """
    return [
        # A3627 Glass & Ceramic items
        {
            "base_name": "SODIUM NITRATE",
            "norms": ["A3627"],
            "filters": [Q(description__icontains="Sodium Nitrate")],
        },
        {
            "base_name": "TITANIUM DIOXIDE",
            "norms": ["A3627"],
            "filters": [
                Q(description__icontains="Titanium Dioxide")
                & Q(description__icontains="other than")
            ],
        },
        {
            "base_name": "SILICA",
            "norms": ["A3627"],
            "filters": [
                Q(hs_code__hs_code__startswith="28110000")
                & Q(description__icontains="Silica")
                & ~Q(description__icontains="Fumed Silica")
            ],
        },
        {
            "base_name": "BORAX",
            "norms": ["A3627"],
            "filters": [
                Q(hs_code__hs_code__startswith="28401900")
                | Q(description__icontains="Borax")
            ],
        },
        {
            "base_name": "RUTILE",
            "norms": ["A3627"],
            "filters": [
                (
                    Q(hs_code__hs_code__startswith="3206")
                    | Q(description__icontains="Glass Formers")
                    | Q(description__icontains="Rutile")
                    | Q(description__icontains="Formers")
                )
                & Q(description__icontains="borax")
            ],
        },
        {
            "base_name": "SODA ASH",
            "norms": ["A3627"],
            "filters": [Q(description__icontains="Soda Ash")],
        },
        {
            "base_name": "CERAMIC COLOUR",
            "norms": ["A3627"],
            "filters": [Q(description__icontains="CERAMIC COLOUR")],
        },
        {
            "base_name": "ALUMINIUM OXIDE, ZINC OXIDE, ZIRCONIUM OXIDE",
            "norms": ["A3627"],
            "filters": [Q(description__icontains="ALUMINIUM OXIDE")],
        },
        {
            "base_name": "PP",
            "norms": ["A3627"],
            "filters": [
                (
                    Q(hs_code__hs_code__startswith="3902")
                    | Q(hs_code__hs_code__startswith="39021000")
                    | Q(description__icontains="Polypropylene")
                    | Q(description__icontains="pp granules")
                    | (
                        Q(description__icontains="packing material")
                        & Q(hs_code__hs_code__startswith="39")
                    )
                )
                & ~Q(description__icontains="BOPP")
                & ~Q(description__icontains="7607")
                & ~Q(description__icontains="ALUMINIUM FOIL")
                & ~Q(hs_code__hs_code__startswith="7607")
                & ~Q(hs_code__hs_code__startswith="4801")
            ],
        },
        # Automotive/Engineering items - C969
        {
            "base_name": "WIRING HANRNESS",
            "norms": ["C969"],
            "filters": [Q(description__icontains="wiring hanrness")],
        },
        {
            "base_name": "WATER PUMP",
            "norms": ["C969"],
            "filters": [Q(description__icontains="WATER PUMP")],
        },
        {
            "base_name": "'O' Ring",
            "norms": ["C969"],
            "filters": [
                Q(description__icontains="'O' Ring")
                | Q(hs_code__hs_code__startswith="40169320")
            ],
        },
        {
            "base_name": "BEARING",
            "norms": ["C969"],
            "filters": [
                Q(description__icontains="BEARING")
                | Q(hs_code__hs_code__startswith="8482")
            ],
        },
        {
            "base_name": "TURBO CHARGER",
            "norms": ["C969"],
            "filters": [Q(description__icontains="TURBO CHARGER")],
        },
        {
            "base_name": "STARTER MOTOR",
            "norms": ["C969"],
            "filters": [Q(description__icontains="starter motor")],
        },
        {
            "base_name": "ALLOY STEEL",
            "norms": ["C969"],
            "filters": [Q(description__icontains="alloy steel rod")],
        },
        {
            "base_name": "AUTOMOTIVE BATTERY",
            "norms": ["C969"],
            "filters": [
                Q(description__icontains="AUTOMOTIVE BATTERY")
                | Q(description__icontains="AUTOMATIVE BATTERY")
                | Q(description__icontains="Automotive Battery")
                | Q(description__icontains="Battery Automotive")
            ],
        },
        {
            "base_name": "BRAKE ASSEMBLY",
            "norms": ["C969"],
            "filters": [Q(description__icontains="Brake Assembly")],
        },
        {
            "base_name": "SEAT ASSEMBLY",
            "norms": ["C969"],
            "filters": [Q(description__icontains="SEAT ASSEMBLY")],
        },
        {
            "base_name": "REARWHEEL TYRE",
            "norms": ["C969"],
            "filters": [Q(description__icontains="REARWHEEL TYRE")],
        },
        {
            "base_name": "FRONTWHEEL TYRE",
            "norms": ["C969"],
            "filters": [Q(description__icontains="frontwheel tyre")],
        },
        {
            "base_name": "RADIATOR",
            "norms": ["C969"],
            "filters": [Q(description__icontains="RADIATOR")],
        },
        {
            "base_name": "REAR WHEELRIM",
            "norms": ["C969"],
            "filters": [Q(description__icontains="REAR WHEELRIM")],
        },
        {
            "base_name": "FRONT WHEELRIM",
            "norms": ["C969"],
            "filters": [Q(description__icontains="FRONT WHEELRIM")],
        },
        {
            "base_name": "SAFETY NEUTRAL SWITCH",
            "norms": ["C969"],
            "filters": [Q(description__icontains="SAFETY NEUTRAL SWITCH")],
        },
        {
            "base_name": "OIL SEPERATOR",
            "norms": ["C969"],
            "filters": [Q(description__icontains="OIL SEPERATOR")],
        },
        {
            "base_name": "OIL PUMP",
            "norms": ["C969"],
            "filters": [Q(description__icontains="OIL PUMP")],
        },
        {
            "base_name": "OIL SEAL",
            "norms": ["C969"],
            "filters": [Q(description__icontains="Oil Seal")],
        },
        {
            "base_name": "CLUTCH ASSEMBLY",
            "norms": ["C969"],
            "filters": [Q(description__icontains="CLUTCH ASSEMBLY")],
        },
        {
            "base_name": "ALTERNATOR",
            "norms": ["C969"],
            "filters": [Q(description__icontains="ALTERNATOR")],
        },
        {
            "base_name": "HYDROSTATIC TRANSMISSION",
            "norms": ["C969"],
            "filters": [
                Q(description__icontains="HYDROSTATIC")
                & Q(description__icontains="TRANSMISSION")
            ],
        },
        {
            "base_name": "HYDRAULIC VALVES",
            "norms": ["C969"],
            "filters": [Q(description__icontains="HYDRAULIC VALVES")],
        },
        {
            "base_name": "HYDRAULIC CYLINDER",
            "norms": ["C969"],
            "filters": [Q(description__icontains="HYDRAULIC CYLINDER")],
        },
        {
            "base_name": "HYDRAULIC PUMP",
            "norms": ["C969"],
            "filters": [Q(description__icontains="HYDRAULIC PUMP")],
        },
        {
            "base_name": "FRONT AXLE",
            "norms": ["C969"],
            "filters": [Q(description__icontains="FRONT AXLE")],
        },
        {
            "base_name": "FUEL FILTER",
            "norms": ["C969"],
            "filters": [Q(description__icontains="FUEL FILTER")],
        },
        {
            "base_name": "FUEL INJECTION PUMP",
            "norms": ["C969"],
            "filters": [Q(description__icontains="FUEL INJECTION PUMP")],
        },
        {
            "base_name": "INTERNAL COMBUSTION ENGINE",
            "norms": ["C969"],
            "filters": [Q(description__icontains="INTERNAL COMBUSTION ENGINE")],
        },
        {
            "base_name": "AIR FILTER",
            "norms": ["C969"],
            "filters": [Q(description__icontains="AIR FILTER")],
        },
        {
            "base_name": "AUXILIARY VALVES",
            "norms": ["C969"],
            "filters": [Q(description__icontains="AUXILIARY VALVES")],
        },
        {
            "base_name": "SYNCHROPACKS",
            "norms": ["C969"],
            "filters": [Q(description__icontains="synchropacks")],
        },
        # Steel items - C473, C471
        {
            "base_name": "HOT ROLLED STEEL",
            "norms": ["C473", "C471", "C969"],
            "filters": [
                Q(description__icontains="HOT ROLLED")
                | Q(description__icontains="NON ALLOY")
            ],
        },
        {
            "base_name": "COLD ROLLED STEEL",
            "norms": ["C473", "C471", "C969"],
            "filters": [Q(description__icontains="COLD ROLLED")],
        },
        # Food ingredients - multiple norms
        {
            "base_name": "SUGAR",
            "norms": ["E1", "E5"],
            "filters": [
                Q(description__icontains="sugar")
                | Q(description__icontains="1701")
                | Q(hs_code__hs_code__startswith="1701")
            ],
        },
        {
            "base_name": "WHEAT GLUTEN",
            "norms": ["E5"],
            "filters": [
                Q(description__icontains="GLUTEN")
                | Q(description__icontains="1109")
                | Q(hs_code__hs_code__startswith="1109")
            ],
        },
        {
            "base_name": "WHEAT FLOUR",
            "norms": ["E5"],
            "filters": [
                Q(description__icontains="WHEAT FLOUR")
                | Q(description__icontains="FLOUR")
            ],
        },
        {
            "base_name": "DIETARY FIBRE",
            "norms": ["E5"],
            "filters": [Q(description__icontains="Dietary Fibre")],
        },
        {
            "base_name": "CHEESE",
            "norms": ["E1", "E5"],
            "filters": [
                Q(description__icontains="0406")
                | Q(hs_code__hs_code__startswith="0406")
            ],
        },
        # E132 Cheese detection is strict (Auto Planning business rules) — one
        # of 0401/0405/0406 (HSN or description) AND the description contains
        # BOTH "vegetable" and "oil". Kept as its own norm-scoped entry (not
        # merged into the loose E1/E5 CHEESE rule above) so tightening this
        # for E132 never changes E1/E5 item-name linking.
        {
            "base_name": "CHEESE",
            "norms": ["E132"],
            "filters": [
                (
                    Q(description__icontains="0401")
                    | Q(hs_code__hs_code__startswith="0401")
                    | Q(description__icontains="0405")
                    | Q(hs_code__hs_code__startswith="0405")
                    | Q(description__icontains="0406")
                    | Q(hs_code__hs_code__startswith="0406")
                )
                & Q(description__icontains="vegetable")
                & Q(description__icontains="oil")
            ],
        },
        {
            "base_name": "DWP",
            "norms": ["E1", "E5", "E32"],
            "filters": [
                Q(description__icontains="0404")
                | Q(hs_code__hs_code__startswith="0404")
            ],
        },
        {
            "base_name": "SWP",
            "norms": ["E1", "E5", "E32"],
            "filters": [
                Q(description__icontains="0404")
                | Q(hs_code__hs_code__startswith="0404")
            ],
        },
        {
            "base_name": "ANTI OXIDANT",
            "norms": ["E1", "E5"],
            "filters": [
                Q(description__icontains="Anti oxidant")
                | Q(description__icontains="Anti oxident")
            ],
        },
        {
            "base_name": "FOOD COLOUR",
            "norms": ["E1", "E5"],
            "filters": [Q(description__icontains="FOOD COLOUR")],
        },
        {
            "base_name": "STARCH 1108",
            "norms": ["E1", "E5"],
            "filters": [
                Q(description__icontains="1108")
                | Q(hs_code__hs_code__startswith="1108")
            ],
        },
        {
            "base_name": "STARCH 3505",
            "norms": ["E1", "E5"],
            "filters": [
                Q(description__icontains="3505")
                | Q(hs_code__hs_code__startswith="3505")
                | (
                    Q(description__icontains="starch")
                    & (
                        ~Q(hs_code__hs_code__startswith="1108")
                        | ~Q(description__icontains="1108")
                    )
                )
            ],
        },
        {
            "base_name": "LEAVENING AGENT",
            "norms": ["E5"],
            "filters": [
                Q(description__icontains="LEAVENING AGENT")
                | Q(description__icontains="leaving agent")
                | Q(description__icontains="Yeast")
            ],
        },
        {
            "base_name": "OLIVE OIL",
            "norms": ["E5", "E126"],
            "filters": [
                Q(description__icontains="1500")
                | Q(description__icontains="1509")
                | Q(description__icontains="1510")
                | Q(hs_code__hs_code__startswith="1509")
            ],
        },
        {
            "base_name": "RBD PALMOLEIN OIL",
            "norms": ["E1", "E5", "E126"],
            "filters": [
                Q(description__icontains="vegetable shortening")
                | Q(description__icontains="rbd palmolein oil")
                | Q(hs_code__hs_code__startswith="15119020")
            ],
            "is_active": False,
        },
        # E132 RBD Palmolein Oil detection (Auto Planning business rules) —
        # HSN 1510 (or "1510" in the description), scoped to E132 only so it
        # never changes E1/E5/E126 item-name linking above.
        {
            "base_name": "RBD PALMOLEIN OIL",
            "norms": ["E132"],
            "filters": [
                Q(hs_code__hs_code__startswith="1510")
                | Q(description__icontains="1510")
            ],
            "is_active": True,
        },
        {
            "base_name": "PALM KERNEL OIL",
            "norms": ["E1", "E5", "E126", "E132"],
            "filters": [
                Q(hs_code__hs_code__startswith="1513")
                | Q(description__icontains="1513")
            ],
        },
        {
            "base_name": "LIQUID GLUCOSE",
            "norms": ["E1"],
            "filters": [Q(description__icontains="liquid glucose")],
        },
        {
            "base_name": "ESSENTIAL OIL",
            "norms": ["E1"],
            "filters": [
                Q(description__icontains="relevant essential oils")
                | Q(description__icontains="ESSENTIAL OILS")
                | Q(description__icontains="Essential Oil")
            ],
        },
        {
            "base_name": "CEREALS FLAKES",
            "norms": ["E132"],
            "filters": [
                Q(description__icontains="Chickpeas")
                | Q(description__icontains="lentils")
                | Q(description__icontains="Cereal Flakes")
                | Q(description__icontains="Green Peas")
            ],
        },
        {
            "base_name": "RELEVANT ADDITIVES DESCRIPTION",
            "norms": ["E132"],
            "filters": [
                Q(description__icontains="RELEVANT ADDITIVES DESCRIPTION")
                | Q(description__icontains="Methyl Cellulose")
            ],
        },
        {
            "base_name": "STABILIZING AGENT",
            "norms": ["E1"],
            "filters": [Q(description__icontains="Stabilizing Agent")],
        },
        {
            "base_name": "WPC",
            "norms": ["E1", "E5", "E132"],
            "filters": [
                Q(description__icontains="3502")
                | Q(hs_code__hs_code__startswith="3502")
                | Q(description__icontains="WPC")
            ],
        },
        {
            "base_name": "EMULSIFIER",
            "norms": ["E1"],
            "filters": [
                Q(description__icontains="emulsifier")
                | Q(description__icontains="EMULSIFIER")
            ],
        },
        {
            "base_name": "COCOA PASTE",
            "norms": ["E5", "E1", "E132"],
            "filters": [
                Q(description__icontains="Cocoa Paste")
                | Q(description__icontains="1803")
                | Q(hs_code__hs_code__startswith="1803")
            ],
        },
        {
            "base_name": "FRUIT/COCOA",
            "norms": ["E1", "E5"],
            "filters": [
                Q(
                    Q(description__icontains="Cocoa")
                    | Q(description__icontains="Coco Powder")
                    | Q(description__icontains="Cocoa Powder")
                    | Q(description__icontains="1802")
                    | Q(description__icontains="1804")
                    | Q(description__icontains="18050000")
                    | Q(description__icontains="COCO POWDER")
                    | Q(hs_code__hs_code__startswith="18050000")
                    | Q(description__icontains="fruit/cocoa")
                )
                & ~Q(description__icontains="actual user")
                # Exclude Cocoa Paste items (go to COCOA PASTE category instead)
                & ~Q(description__icontains="Cocoa Paste")
                & ~Q(description__icontains="1803")
                & ~Q(hs_code__hs_code__startswith="1803")
                # Exclude oil-category items (HSN 1511/1513, Vegetable Oil, Palmolein, Palm Kernel)
                & ~Q(hs_code__hs_code__startswith="1511")
                & ~Q(hs_code__hs_code__startswith="1513")
                & ~Q(description__icontains="Vegetable Oil")
                & ~Q(description__icontains="Palmolein")
                & ~Q(description__icontains="Palm Kernel")
                & ~Q(description__icontains="1511")
                & ~Q(description__icontains="1513")
            ],
        },
        {
            "base_name": "FRUIT JUICE",
            "norms": ["E1", "E5"],
            "filters": [
                Q(description__icontains="Juice")
                | Q(description__icontains="Fruit Concentrate")
                | Q(description__icontains="Relevant fruit")
                | Q(description__icontains="FRUITS FLAVOUR")
                | Q(description__icontains="Fruit Flavour")
                | Q(description__icontains="2009")
                | Q(hs_code__hs_code__startswith="2009")
            ],
        },
        {
            "base_name": "FRUIT COCKTAIL",
            "norms": ["E1"],
            "filters": [
                (Q(description__icontains="2008") & Q(description__icontains="Fruit"))
                | Q(hs_code__hs_code__startswith="2008")
            ],
        },
        {
            "base_name": "FOOD FLAVOUR",
            "norms": ["E126"],
            "filters": [
                Q(
                    Q(description__icontains="0908")
                    | Q(description__icontains="0802")
                    | Q(description__icontains="0806")
                    | Q(hs_code__hs_code__startswith="0908")
                    | Q(hs_code__hs_code__startswith="0802")
                    | Q(hs_code__hs_code__startswith="0806")
                )
            ],
        },
        {
            "base_name": "FOOD FLAVOUR",
            "norms": ["E1", "E5", "E126", "E132"],
            "filters": [
                Q(
                    Q(description__icontains="relevant food flavour")
                    | Q(description__icontains="Relevant Food Grade Flavours")
                    | Q(description__icontains="FOOD FLAVOUR")
                    | Q(description__icontains="relevant (food flour")
                    | Q(description__icontains="Flavouring Agent")
                    | Q(description__icontains="Cardamom")
                )
                & Q(
                    Q(description__icontains="0908")
                    | Q(description__icontains="0802")
                    | Q(description__icontains="0806")
                    | Q(hs_code__hs_code__startswith="0908")
                    | Q(hs_code__hs_code__startswith="0802")
                    | Q(hs_code__hs_code__startswith="0806")
                )
                & ~Q(description__icontains="other")
            ],
        },
        {
            "base_name": "CITRIC ACID / TARTARIC ACID",
            "norms": ["E1", "E5"],
            "filters": [
                Q(description__icontains="CITRIC ACID")
                | Q(description__icontains="TARTARIC ACID")
                | Q(description__icontains="TARTARIC AICD")
            ],
        },
        {
            "base_name": "OTHER CONFECTIONERY INGREDIENTS",
            "norms": ["E1"],
            "filters": [
                Q(
                    Q(description__icontains="other")
                    | Q(description__icontains="other confectionery ingredients")
                    | Q(description__icontains="FRUIT FLAVOURS")
                    | Q(description__icontains="nut & nut products")
                    | Q(description__icontains="Fruits and Nuts Product")
                )
                & Q(
                    Q(description__icontains="0908")
                    | Q(description__icontains="0802")
                    | Q(description__icontains="0806")
                    | Q(hs_code__hs_code__startswith="0908")
                    | Q(hs_code__hs_code__startswith="0802")
                    | Q(hs_code__hs_code__startswith="0806")
                )
            ],
        },
        {
            "base_name": "NUTS",
            "norms": ["E1", "E5", "E126"],
            "filters": [
                Q(
                    Q(description__icontains="Nuts")
                    | Q(description__icontains="nut & nut products")
                    | Q(description__icontains="nut")
                    | Q(description__icontains="Fruits and Nuts Product")
                )
                & Q(
                    Q(description__icontains="0802")
                    | Q(hs_code__hs_code__startswith="0802")
                )
            ],
        },
        # E132 Nuts detection (Auto Planning business rules) — 0802 (HSN or
        # description) AND the description contains the WORD "nut" or "nuts"
        # (word-boundary — e.g. must not match "peanut" as a substring).
        # Scoped to E132 only so it never changes E1/E5/E126 item-name linking
        # above.
        {
            "base_name": "NUTS",
            "norms": ["E132"],
            "filters": [
                Q(
                    Q(description__icontains="0802")
                    | Q(hs_code__hs_code__startswith="0802")
                )
                # PostgreSQL's regex engine uses `\y` for a word boundary
                # (Advanced Regular Expressions), NOT the Perl/Python `\b` —
                # `\b` is not a word-boundary escape here.
                & (
                    Q(description__iregex=r"\ynut\y")
                    | Q(description__iregex=r"\ynuts\y")
                )
            ],
        },
        {
            "base_name": "BISCUITS ADDITIVES & INGREDIENTS",
            "norms": ["E5"],
            "filters": [
                Q(description__icontains="BISCUITS ADDITIVES & INGREDIENTS")
                & ~Q(description__icontains="Yeast")
            ],
        },
        {
            "base_name": "SANITATION AND CLEANING CHEMICALS",
            "norms": ["E126"],
            "filters": [Q(description__icontains="SANITATION AND CLEANING CHEMICALS")],
        },
        {
            "base_name": "CMC",
            "norms": ["E132"],
            "filters": [
                Q(description__icontains="TBHQ")
                | Q(description__icontains="3912")
                | Q(hs_code__hs_code__startswith="3912")
                | Q(description__icontains="Cellulose")
            ],
        },
        {
            "base_name": "RAISIN",
            "norms": ["E1", "E5", "E126", "E132"],
            "filters": [
                Q(description__icontains="0806")
                | Q(hs_code__hs_code__startswith="0806")
            ],
            "is_active": False,
        },
        {
            "base_name": "WALNUT",
            "norms": ["E1", "E5", "E126", "E132"],
            "filters": [
                Q(description__icontains="0802")
                | Q(hs_code__hs_code__startswith="0802")
            ],
            "is_active": False,
        },
        {
            "base_name": "CARDAMOM",
            "norms": ["E1", "E5", "E126", "E132"],
            "filters": [
                Q(description__icontains="0908")
                | Q(hs_code__hs_code__startswith="0908")
            ],
            "is_active": False,
        },
        # Packaging materials - COMMON and E1, E5, E132, E126
        #
        # PP / HDPE / LDPE / PAPER / PAPER BOARD are now handled exclusively
        # by the classify_packaging_item() engine below (applied ahead of
        # this whole function for any norm in SUPPORTED_PACKAGING_NORMS) —
        # they are no longer defined here to avoid two rule engines
        # disagreeing on the same five categories. BOPP and ALUMINIUM FOIL
        # aren't part of that engine, so they stay as ordinary filters.
        {
            "base_name": "BOPP",
            "norms": ["COMMON", "E1", "E5", "E132", "E126"],
            "filters": [
                Q(description__icontains="BOPP")
                & ~Q(description__icontains="7607")
                & ~Q(description__icontains="ALUMINIUM FOIL")
                & ~Q(hs_code__hs_code__startswith="7607")
                & ~Q(hs_code__hs_code__startswith="4801")
            ],
        },
        {
            "base_name": "ALUMINIUM FOIL",
            "norms": ["COMMON", "E1", "E5", "E132", "E126"],
            "filters": [
                Q(hs_code__hs_code__startswith="7607")
                | Q(description__icontains="7607")
            ],
        },
        # Miscellaneous - COMMON
        {
            "base_name": "COKE",
            "norms": ["COMMON"],
            "filters": [Q(description__icontains="COKE")],
        },
        {
            "base_name": "BETEL NUT",
            "norms": ["COMMON"],
            "filters": [Q(description__icontains="BETEL NUT")],
        },
        {
            "base_name": "SUPARI WHOLE",
            "norms": ["COMMON"],
            "filters": [Q(description__icontains="SUPARI WHOLE")],
        },
        {
            "base_name": "COFFEE BEANS",
            "norms": ["COMMON"],
            "filters": [Q(description__icontains="Coffee Beans")],
        },
        {
            "base_name": "PICKLE",
            "norms": ["E126"],
            "filters": [
                Q(description__icontains="pickle")
                & ~Q(description__icontains="food additive")
            ],
        },
    ]


# ─── Packaging pre-classification (all supported norms) ────────────────────
#
# Generic HSN/description rule engine for packaging materials — PP, HDPE,
# LDPE (LLDPE folds into LDPE), Paper, and Paper Board. Runs BEFORE the
# generic `get_item_filters()` matcher, for any norm in
# SUPPORTED_PACKAGING_NORMS: the classifier itself only ever returns a bare
# packaging name ('PP', 'HDPE', 'LDPE', 'PAPER', 'PAPER BOARD'); the caller
# appends " - <the licence's matching packaging norm>" and resolves/creates
# that exact ItemNameModel row (case-insensitively, never duplicating).
# This is the single rule engine for these five packaging categories — it
# is not duplicated per norm, and a new norm only needs adding to
# SUPPORTED_PACKAGING_NORMS to pick it up, no new classification logic.
# Falls through to the existing matcher unchanged whenever none of its
# rules match, or when the licence carries no supported packaging norm.

_PACKAGING_NAMES: tuple[str, ...] = ('PP', 'HDPE', 'LDPE', 'PAPER', 'PAPER BOARD')

# Norms the packaging engine is allowed to tag. A licence's norm classes are
# intersected with this set (in the licence's own norm-class order) to pick
# a single deterministic "current norm" — never an arbitrary norm_classes[0]
# from a queryset with no defined ordering, and never a norm packaging was
# never scoped to (e.g. A3627, C969) just because it happens to be listed
# first for some licence.
SUPPORTED_PACKAGING_NORMS: frozenset[str] = frozenset({
    'COMMON', 'PP', 'E1', 'E5', 'E126', 'E132',
})


def _resolve_packaging_norm(norm_classes) -> str | None:
    """First of the licence's own norm classes that the packaging engine
    supports, or ``None`` if the licence carries no supported packaging
    norm at all (caller must skip packaging classification entirely in
    that case)."""
    for norm in norm_classes:
        if norm in SUPPORTED_PACKAGING_NORMS:
            return norm
    return None

_PACKAGING_GSM_UNIT = r'G\.?\s*S\.?\s*M\.?(?![A-Z0-9])'
_PACKAGING_GSM_RANGE_RE = re.compile(r'(\d+)\s*(?:-|TO|/|~)\s*(\d+)\s*' + _PACKAGING_GSM_UNIT)
_PACKAGING_GSM_SINGLE_RE = re.compile(r'(\d+)\s*' + _PACKAGING_GSM_UNIT)


def _packaging_normalize(text) -> str:
    """Upper-case + punctuation-stripped + whitespace-collapsed text, for
    packaging keyword containment checks only. Punctuation (-, _, ., /, ,)
    is replaced with a space so hyphenated variants ('HIGH-DENSITY
    POLYETHYLENE') match the same as spaced ones."""
    text = (text or '').upper()
    for ch in ('-', '_', '.', '/', ','):
        text = text.replace(ch, ' ')
    return ' '.join(text.split())


def _packaging_hsn_digits(hs_code) -> str:
    """Digits-only HSN for prefix matching (ignores spaces/dashes/case)."""
    return ''.join(c for c in (hs_code or '') if c.isdigit())


def extract_gsm_range(description) -> tuple[int, int] | None:
    """Extract a ``(min_gsm, max_gsm)`` pair from free-text GSM mentions.

    Recognises a single value ('70 GSM', '70GSM', '70 G.S.M.') and ranges
    joined by '-', 'TO', '/', or '~' ('40-100 GSM', '40 TO 100 GSM',
    '40/100 GSM', '40~100 GSM'). Only whitespace is collapsed before
    matching — punctuation is left intact because '-', '/' and '~' are
    meaningful range separators here. Returns ``None`` when no GSM figure
    is present.
    """
    text = ' '.join((description or '').upper().split())
    match = _PACKAGING_GSM_RANGE_RE.search(text)
    if match:
        a, b = int(match.group(1)), int(match.group(2))
        return (min(a, b), max(a, b))
    match = _PACKAGING_GSM_SINGLE_RE.search(text)
    if match:
        value = int(match.group(1))
        return (value, value)
    return None


def classify_packaging_item(hs_code: str | None, description: str | None) -> tuple[str, str] | None:
    """Packaging pre-classification — see module-level comment.

    Returns ``(packaging_name, rule_tag)`` — ``packaging_name`` is one of
    :data:`_PACKAGING_NAMES` (bare, with NO norm suffix; the caller appends
    " - <norm>") — for the first matching rule, or ``None`` if nothing
    matches (caller falls back to the existing matcher unchanged). Matching
    is case-insensitive and punctuation-agnostic.

    Priority:
      1. HSN starts with 3902                                     → PP
      2. HSN starts with 3901, or description contains 'HDPE' /
         'HIGH DENSITY POLYETHYLENE'                                → HDPE
      3. description contains 'LLDPE' / 'LINEAR LOW DENSITY
         POLYETHYLENE' — checked BEFORE the plain LDPE keywords:
         both map to the same bucket, but every LLDPE token is a
         superstring of an LDPE token ("LLDPE" contains "LDPE",
         "LINEAR LOW DENSITY POLYETHYLENE" contains "LOW DENSITY
         POLYETHYLENE"), so checking LDPE first would always win and
         the debug log would misreport LLDPE items as plain LDPE      → LDPE
      4. description contains 'LDPE' / 'LOW DENSITY POLYETHYLENE'   → LDPE
      5. description contains 'PAPER' and extracted GSM has
         min >= 40 and max <= 150                                   → PAPER
      6. description contains 'PAPER' and extracted max GSM > 150   → PAPER BOARD

    HSN 7607 is handled exclusively by the ALUMINIUM FOIL entry in
    ``get_item_filters()`` — checked first, ahead of every rule above, so a
    7607 item is never classified as PP/HDPE/LDPE/PAPER/PAPER BOARD.
    """
    hs = _packaging_hsn_digits(hs_code)
    desc = _packaging_normalize(description)

    if hs.startswith('7607') or '7607' in desc:
        return None

    if hs.startswith('3902'):
        return 'PP', 'RULE_PP'

    if hs.startswith('3901') or 'HDPE' in desc or 'HIGH DENSITY POLYETHYLENE' in desc:
        return 'HDPE', 'RULE_HDPE'

    if 'LLDPE' in desc or 'LINEAR LOW DENSITY POLYETHYLENE' in desc:
        return 'LDPE', 'RULE_LLDPE'

    if 'LDPE' in desc or 'LOW DENSITY POLYETHYLENE' in desc:
        return 'LDPE', 'RULE_LDPE'

    if 'PAPER' in desc:
        gsm = extract_gsm_range(description)
        if gsm:
            min_gsm, max_gsm = gsm
            if max_gsm > 150:
                return 'PAPER BOARD', 'RULE_PAPER_BOARD'
            if min_gsm >= 40:
                return 'PAPER', 'RULE_PAPER'

    return None


def _get_or_create_packaging_item_name(packaging_name: str, norm: str):
    """Case-insensitive get-or-create for ``"<packaging_name> - <norm>"``.
    Reuses an existing ``ItemNameModel`` row regardless of case, never
    creates a duplicate. Ties a newly-created row to the ``norm``'s own
    ``SionNormClassModel`` (falling back to no norm, same as
    ``ensure_plan_item_names``, if that norm class doesn't exist in the
    database)."""
    from apps.core.models import ItemNameModel, SionNormClassModel

    name = f"{packaging_name} - {norm}"
    existing = ItemNameModel.objects.filter(name__iexact=name).first()
    if existing:
        return existing

    norm_obj = SionNormClassModel.objects.filter(norm_class=norm).first()
    obj, _ = ItemNameModel.objects.get_or_create(
        name=name,
        defaults={'sion_norm_class': norm_obj, 'is_active': True},
    )
    return obj


def bulk_auto_link_license_items(license_instance):
    """
    Bulk auto-link ItemNameModel rows to all unlinked import items on a
    licence. Runs ~M queries (one per filter config that applies to this
    licence's norms) instead of N×M (one per item × filter), and writes M2M
    rows via bulk_create.

    Returns the number of import items that had ItemNames linked.

    SAFE to call after the per-item signal cascade has been suspended —
    this does the same work the post_save signal would have done one-at-a-time,
    just batched.
    """
    from functools import reduce
    from operator import or_
    from django.db.models import Count
    from apps.core.models import ItemNameModel
    from apps.license.models import LicenseImportItemsModel

    norm_classes = list(
        license_instance.export_license.values_list("norm_class__norm_class", flat=True).distinct()
    )
    if not norm_classes:
        return 0

    # Items already linked to ItemNames are skipped.
    unlinked_ids = list(
        LicenseImportItemsModel.objects
        .filter(license=license_instance)
        .annotate(_link_count=Count("items"))
        .filter(_link_count=0)
        .values_list("id", flat=True)
    )
    if not unlinked_ids:
        return 0

    filter_configs = get_item_filters()
    needed_names = set()  # (base_name, norm) pairs we'll look up
    item_to_basenames: dict[int, list[tuple[str, str]]] = {}
    name_to_obj: dict[str, ItemNameModel] = {}

    # Packaging pre-classification — runs BEFORE the generic filter loop,
    # for any licence norm the packaging engine supports (see
    # classify_packaging_item / SUPPORTED_PACKAGING_NORMS). The first of the
    # licence's own norm classes that's in that supported set is used as
    # "<PACKAGING_NAME> - <norm>" — never an arbitrary norm_classes[0], and
    # never a norm packaging isn't scoped to. Matched items are resolved
    # directly (not via the sion_norm_class__norm_class__in=norm_classes
    # query below, so resolution never depends on how that query is scoped)
    # and excluded from the generic pass so they are never double-matched
    # by an unrelated filter config.
    current_packaging_norm = _resolve_packaging_norm(norm_classes)
    remaining_unlinked_ids = unlinked_ids
    if current_packaging_norm is not None:
        packaging_candidates = (
            LicenseImportItemsModel.objects
            .filter(id__in=unlinked_ids)
            .select_related('hs_code')
        )
        for ii in packaging_candidates:
            hs_code_str = ii.hs_code.hs_code if ii.hs_code_id else None
            pkg_match = classify_packaging_item(hs_code_str, ii.description)
            if not pkg_match:
                continue
            packaging_name, rule_tag = pkg_match
            logger.debug(
                "bulk_auto_link_license_items: %s matched import item %s -> %r",
                rule_tag, ii.id, f"{packaging_name} - {current_packaging_norm}",
            )
            item_name_obj = _get_or_create_packaging_item_name(packaging_name, current_packaging_norm)
            name_to_obj[item_name_obj.name] = item_name_obj
            item_to_basenames.setdefault(ii.id, []).append(item_name_obj.name)
        if item_to_basenames:
            remaining_unlinked_ids = [iid for iid in unlinked_ids if iid not in item_to_basenames]

    for item_config in filter_configs:
        applicable_norms = [n for n in norm_classes if n in item_config["norms"]]
        if not applicable_norms:
            continue
        combined_q = reduce(or_, item_config["filters"])
        matching_ids = list(
            LicenseImportItemsModel.objects
            .filter(id__in=remaining_unlinked_ids)
            .filter(combined_q)
            .values_list("id", flat=True)
        )
        if not matching_ids:
            continue
        base_name = f"{item_config['base_name']} - {applicable_norms[0]}"
        needed_names.add(base_name)
        for iid in matching_ids:
            item_to_basenames.setdefault(iid, []).append(base_name)

    if not item_to_basenames:
        return 0

    # Resolve the generic-filter ItemNames in a single query (PP-norm names
    # were already resolved above and are already in name_to_obj).
    if needed_names:
        name_to_obj.update({
            it.name: it
            for it in ItemNameModel.objects
            .filter(name__in=needed_names, sion_norm_class__norm_class__in=norm_classes)
        })
    if not name_to_obj:
        return 0

    # Bulk-insert M2M rows.
    Through = LicenseImportItemsModel.items.through
    rows = []
    # `is_restricted` is no longer set from ItemNameModel.restriction_percentage —
    # it's derived from condition_type via the model's save() override.
    for iid, base_names in item_to_basenames.items():
        for bn in base_names:
            item_name = name_to_obj.get(bn)
            if not item_name:
                continue
            rows.append(Through(
                licenseimportitemsmodel_id=iid,
                itemnamemodel_id=item_name.id,
            ))

    if rows:
        Through.objects.bulk_create(rows, ignore_conflicts=True)

    return len(item_to_basenames)


def match_import_item_to_items(import_item, license_norm_classes):
    """
    Match a single import item to ItemNameModel items based on comprehensive filters.

    Args:
        import_item: LicenseImportItemsModel instance
        license_norm_classes: List of norm class strings for the license

    Returns:
        QuerySet: ItemNameModel items that match this import item
    """
    from apps.core.models import ItemNameModel
    from apps.license.models import LicenseImportItemsModel

    if not license_norm_classes:
        return ItemNameModel.objects.none()

    # Packaging pre-classification — runs BEFORE the generic filter loop,
    # for any licence norm the packaging engine supports (see
    # classify_packaging_item / SUPPORTED_PACKAGING_NORMS). A match here
    # short-circuits the generic matcher entirely for this item, resolved
    # against the first of the licence's own norm classes that's in that
    # supported set — never an arbitrary license_norm_classes[0]. No
    # supported norm, or no rule match, falls through unchanged.
    current_packaging_norm = _resolve_packaging_norm(license_norm_classes)
    if current_packaging_norm is not None:
        hs_code_str = import_item.hs_code.hs_code if import_item.hs_code_id else None
        pkg_match = classify_packaging_item(hs_code_str, import_item.description)
        if pkg_match:
            packaging_name, rule_tag = pkg_match
            logger.debug(
                "match_import_item_to_items: %s matched import item %s -> %r",
                rule_tag, import_item.id, f"{packaging_name} - {current_packaging_norm}",
            )
            item_name_obj = _get_or_create_packaging_item_name(packaging_name, current_packaging_norm)
            return ItemNameModel.objects.filter(id=item_name_obj.id)

    filters = get_item_filters()
    matched_item_ids = set()
    import_item_qs = LicenseImportItemsModel.objects.filter(id=import_item.id)

    for item_config in filters:
        # Check if this item config applies to any of the license norms.
        applicable_norms = [norm for norm in license_norm_classes if norm in item_config['norms']]
        if not applicable_norms:
            continue

        # Check if the import item matches any of the filters for this item type
        for filter_q in item_config['filters']:
            # Create a queryset with just this import item and apply the filter
            test_qs = import_item_qs.filter(filter_q)

            if test_qs.exists():
                # This import item matches this filter, find the corresponding ItemNameModel
                item_name = f"{item_config['base_name']} - {applicable_norms[0]}"

                # Try to find the ItemNameModel (it might not exist yet)
                matching_items = ItemNameModel.objects.filter(
                    name=item_name,
                    sion_norm_class__norm_class__in=license_norm_classes
                )

                matched_item_ids.update(matching_items.values_list("id", flat=True))
                break  # Found a match for this item config, move to next

    # Return unique ItemNameModel items
    if matched_item_ids:
        return ItemNameModel.objects.filter(id__in=matched_item_ids)

    return ItemNameModel.objects.none()
