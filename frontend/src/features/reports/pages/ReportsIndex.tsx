import { Link } from 'react-router-dom'
import {
  FileText,
  BarChart2,
  Table,
  BookOpen,
  ScrollText,
  Clock,
  ListChecks,
  Download,
} from 'lucide-react'

interface ReportCard {
  title: string
  description: string
  icon: React.ComponentType<{ className?: string }>
  href: string
  group?: string
}

const REPORT_CARDS: ReportCard[] = [
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

const SION_CARDS: ReportCard[] = [
  {
    title: 'SION Norm E1',
    description: 'Parle DFIA report for SION norm E1, grouped by notification.',
    icon: ScrollText,
    href: '/reports/parle/sion-e1',
    group: 'Parle',
  },
  {
    title: 'SION Norm E5',
    description: 'Parle DFIA report for SION norm E5, grouped by notification.',
    icon: ScrollText,
    href: '/reports/parle/sion-e5',
    group: 'Parle',
  },
  {
    title: 'SION Norm E126',
    description: 'Parle DFIA report for SION norm E126, grouped by notification.',
    icon: ScrollText,
    href: '/reports/parle/sion-e126',
    group: 'Parle',
  },
  {
    title: 'SION Norm E132',
    description: 'Parle DFIA report for SION norm E132, grouped by notification.',
    icon: ScrollText,
    href: '/reports/parle/sion-e132',
    group: 'Parle',
  },
]

const EXPORT_CARDS: ReportCard[] = [
  {
    title: 'Expiring Licenses',
    description: 'Export licenses expiring within N days as Excel.',
    icon: Clock,
    href: '/reports/expiring-licenses',
  },
  {
    title: 'Active Licenses',
    description: 'Export active licenses from the last N days as Excel.',
    icon: ListChecks,
    href: '/reports/active-licenses',
  },
  {
    title: 'Download License',
    description: 'Per-license balance summary by number or status.',
    icon: Download,
    href: '/reports/download-license',
  },
]

function CardGrid({ cards }: { cards: ReportCard[] }) {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Link
          key={card.href}
          to={card.href}
          className="space-y-2 rounded-lg border bg-card p-6 transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
        >
          <card.icon className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
          <h2 className="font-semibold">{card.title}</h2>
          <p className="text-sm text-muted-foreground">{card.description}</p>
        </Link>
      ))}
    </div>
  )
}

export default function ReportsIndex() {
  return (
    <div className="space-y-8 p-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Reports</h1>
        <p className="mt-1 text-muted-foreground">
          Generate and download async reports. Reports are queued and available for download when
          ready.
        </p>
      </div>

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Async Reports
        </h2>
        <CardGrid cards={REPORT_CARDS} />
      </section>

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          SION Parle Reports
        </h2>
        <CardGrid cards={SION_CARDS} />
      </section>

      <section>
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          License Exports
        </h2>
        <CardGrid cards={EXPORT_CARDS} />
      </section>
    </div>
  )
}
