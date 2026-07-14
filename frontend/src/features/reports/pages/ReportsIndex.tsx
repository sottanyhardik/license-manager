import { Link } from 'react-router-dom'
import { FileText, BarChart2, Table, BookOpen } from 'lucide-react'

const REPORT_CARDS = [
  {
    title: 'Balance Report',
    description: 'License balance summary. PDF or Excel.',
    icon: FileText,
    href: '/reports/balance',
  },
  {
    title: 'Item Report',
    description: 'Per-item utilisation across licenses.',
    icon: BarChart2,
    href: '/reports/items',
  },
  {
    title: 'Pivot Report',
    description: 'Items grouped by SION norm class.',
    icon: Table,
    href: '/reports/pivot',
  },
  {
    title: 'Ledger Report',
    description: 'License transaction ledger.',
    icon: BookOpen,
    href: '/reports/ledger',
  },
]

export default function ReportsIndex() {
  return (
    <div className="space-y-6 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
        <p className="text-muted-foreground mt-1">
          Generate and download async reports. Reports are queued and available for download when
          ready.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {REPORT_CARDS.map((card) => (
          <Link
            key={card.href}
            to={card.href}
            className="rounded-lg border bg-card p-6 hover:bg-accent transition-colors space-y-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
          >
            <card.icon className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
            <h2 className="font-semibold">{card.title}</h2>
            <p className="text-sm text-muted-foreground">{card.description}</p>
          </Link>
        ))}
      </div>
    </div>
  )
}
