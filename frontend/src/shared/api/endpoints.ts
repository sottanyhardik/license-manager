export const ENDPOINTS = {
  AUTH: {
    LOGIN: '/api/v1/auth/login/',
    LOGOUT: '/api/v1/auth/logout/',
    REFRESH: '/api/v1/auth/token/refresh/',
    ME: '/api/v1/auth/me/',
  },
  LICENSES: {
    LIST: '/api/v1/licenses/',
    DETAIL: (id: number | string) => `/api/v1/licenses/${id}/`,
    ITEMS: (id: number | string) => `/api/v1/licenses/${id}/items/`,
    BALANCE: (id: number | string) => `/api/v1/licenses/${id}/balance/`,
    ITEM_USAGE: (id: number | string) => `/api/v1/licenses/${id}/item-usage/`,
    BALANCE_PDF: (id: number | string) => `/api/v1/licenses/${id}/balance-pdf/`,
    BALANCE_EXCEL: '/api/v1/licenses/balance-excel/',
    GENERATE_PDF: (id: number | string) => `/api/v1/licenses/${id}/generate-pdf/`,
    MERGED_DOCUMENTS: (id: number | string) => `/api/v1/licenses/${id}/merged-documents/`,
    SEARCH: '/api/v1/licenses/search/',
  },
  ALLOTMENTS: {
    LIST: '/api/v1/allotments/',
    DETAIL: (id: number | string) => `/api/v1/allotments/${id}/`,
  },
  TRADES: {
    LIST: '/api/v1/trades/',
    DETAIL: (id: number | string) => `/api/v1/trades/${id}/`,
  },
  BILLS_OF_ENTRY: {
    LIST: '/api/v1/bills-of-entry/',
    DETAIL: (id: number | string) => `/api/v1/bills-of-entry/${id}/`,
    UPDATE_INVOICE: (id: number | string) => `/api/v1/bills-of-entry/${id}/update-invoice/`,
  },
  INCENTIVE_LICENSES: {
    LIST: '/api/v1/incentive-licenses/',
    DETAIL: (id: number | string) => `/api/v1/incentive-licenses/${id}/`,
  },
  USERS: {
    LIST: '/api/v1/users/',
    DETAIL: (id: number | string) => `/api/v1/users/${id}/`,
  },
  REPORTS: {
    LIST: '/api/v1/reports/',
  },
  LEDGER: {
    UPLOAD: '/api/v1/ledger/upload/',
    LIST: '/api/v1/ledger/',
  },
  TRANSFER_LETTERS: {
    LIST: '/api/v1/transfer-letters/',
    GENERATE: '/api/v1/transfer-letters/generate/',
  },
  MASTERS: {
    COMPANIES: '/api/v1/masters/companies/',
    COMPANY: (id: number) => `/api/v1/masters/companies/${id}/`,
    PORTS: '/api/v1/masters/ports/',
    PORT: (id: number) => `/api/v1/masters/ports/${id}/`,
    HS_CODES: '/api/v1/masters/hs-codes/',
    HS_CODE: (id: number) => `/api/v1/masters/hs-codes/${id}/`,
    ITEM_GROUPS: '/api/v1/masters/item-groups/',
    ITEM_GROUP: (id: number) => `/api/v1/masters/item-groups/${id}/`,
    ITEM_NAMES: '/api/v1/masters/item-names/',
    ITEM_NAME: (id: number) => `/api/v1/masters/item-names/${id}/`,
    SION_NORM_CLASSES: '/api/v1/masters/sion-norm-classes/',
    SION_NORM_CLASS: (id: number) => `/api/v1/masters/sion-norm-classes/${id}/`,
    EXCHANGE_RATES: '/api/v1/masters/exchange-rates/',
    EXCHANGE_RATE: (id: number) => `/api/v1/masters/exchange-rates/${id}/`,
  },
} as const
