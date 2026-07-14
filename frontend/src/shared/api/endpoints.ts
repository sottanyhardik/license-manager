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
    BALANCE_EXCEL: '/api/v1/licenses/balance-excel/',
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
} as const
