"""Link Aluminium Foil import items to norm-specific item masters."""

from apps.core.management.commands._item_linking import CommodityItemLinkCommand


class Command(CommodityItemLinkCommand):
    help = 'Link "Aluminium Foil" item variants based on license norm_class and remove other item links'

    commodity_label = "Aluminium Foil"
    hsn_marker = "7607"
    item_prefix = "ALUMINIUM FOIL"
