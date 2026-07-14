// Report feature types

export type ReportFormat = 'pdf' | 'excel' | 'json'

export type TaskStatus = 'pending' | 'running' | 'done' | 'error'

export interface ReportTask {
  task_id: string
  status: TaskStatus
  progress?: number
  file_url: string | null
}

export interface BalanceReportParams {
  license_ids: number[]
  format: ReportFormat
}

export interface ItemReportParams {
  filters: {
    item_name_ids?: number[]
    company_ids?: number[]
    min_balance?: number
    license_status?: 'active' | 'all'
    expiry_date_from?: string
    expiry_date_to?: string
  }
  format: ReportFormat
}

export interface PivotReportParams {
  filters: {
    sion_norm?: string
    company_ids?: number[]
    min_balance?: number
    license_status?: 'active' | 'all'
    expiry_date_from?: string
    expiry_date_to?: string
  }
  format: ReportFormat
}

export interface LedgerReportParams {
  license_id: number
  format: ReportFormat
}
