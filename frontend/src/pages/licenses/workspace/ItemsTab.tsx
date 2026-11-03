import ItemBalanceTable from "@/pages/licence-balances/ItemBalanceTable";
import MovementLedger from "@/pages/licence-balances/MovementLedger";
import type { LicenceDetail } from "@/pages/licence-balances/types";

interface ItemsTabProps {
  detail: LicenceDetail;
  /** The item whose movement ledger is open, from the `item` URL parameter. */
  itemId: number | null;
  onItemChange: (itemId: number | null) => void;
}

/** One row per SR item, with customers and the movement ledger for the item that is open. */
export default function ItemsTab({ detail, itemId, onItemChange }: ItemsTabProps) {
  const selected = itemId === null ? undefined : detail.items.find((item) => item.item_id === itemId);

  return (
    <div className="flex flex-col gap-4">
      <ItemBalanceTable licenceId={detail.licence_id} items={detail.items} onOpenLedger={(id) => onItemChange(id)} />
      {selected ? (
        <MovementLedger
          key={`${detail.licence_id}-${selected.item_id}`}
          licenceId={detail.licence_id}
          itemId={selected.item_id}
          onClose={() => onItemChange(null)}
        />
      ) : null}
    </div>
  );
}
