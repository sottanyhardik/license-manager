"""Link Sugar import items to norm-specific item masters."""

from apps.core.management.commands._item_linking import CommodityItemLinkCommand


class Command(CommodityItemLinkCommand):
    help = 'Link "Sugar" item variants based on license norm_class and remove other item links'

    commodity_label = "Sugar"
    hsn_marker = "1701"
    item_prefix = "SUGAR"
