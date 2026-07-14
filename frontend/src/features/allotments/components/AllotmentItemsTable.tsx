// AllotmentItemsTable — read-only table listing AllotmentItem rows linked to an
// allotment. Intended for the detail view at /allotments/:id.

import type { AllotmentItem } from '../types'

interface AllotmentItemsTableProps {
  items: AllotmentItem[]
}

export function AllotmentItemsTable({ items }: AllotmentItemsTableProps) {
  if (items.length === 0) {
    return (
      <p className="py-4 text-center text-sm text-muted-foreground">No items linked.</p>
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b bg-muted/50">
            <th className="whitespace-nowrap px-3 py-2 text-left font-medium text-muted-foreground">
              License No.
            </th>
            <th className="whitespace-nowrap px-3 py-2 text-left font-medium text-muted-foreground">
              Serial No.
            </th>
            <th className="px-3 py-2 text-left font-medium text-muted-foreground">Description</th>
            <th className="whitespace-nowrap px-3 py-2 text-right font-medium text-muted-foreground">
              Qty
            </th>
            <th className="whitespace-nowrap px-3 py-2 text-right font-medium text-muted-foreground">
              CIF FC ($)
            </th>
            <th className="whitespace-nowrap px-3 py-2 text-right font-medium text-muted-foreground">
              CIF INR (&#x20B9;)
            </th>
            <th className="whitespace-nowrap px-3 py-2 text-left font-medium text-muted-foreground">
              License Date
            </th>
            <th className="whitespace-nowrap px-3 py-2 text-left font-medium text-muted-foreground">
              Expiry
            </th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id} className="border-b last:border-0 hover:bg-muted/30">
              <td className="px-3 py-2 font-mono text-xs">
                {item.license_number ?? '—'}
              </td>
              <td className="px-3 py-2">
                {item.serial_number ?? '—'}
              </td>
              <td className="px-3 py-2">{item.product_description}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.qty}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.cif_fc}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.cif_inr}</td>
              <td className="px-3 py-2 text-sm text-muted-foreground">
                {item.license_date ?? '—'}
              </td>
              <td className="px-3 py-2 text-sm text-muted-foreground">
                {item.license_expiry ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
