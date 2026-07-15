/**
 * Central route path constants.
 * Import from here — never hardcode path strings in components.
 */
export const ROUTES = {
  DASHBOARD: '/',
  LICENSES: '/licenses',
  LICENSE_DETAIL: (id: string | number) => `/licenses/${id}`,
  ALLOTMENTS: '/allotments',
  BOE: '/boe',
  TRADE: '/trade',
  REPORTS: {
    BALANCE: '/reports/balance',
    ITEMS: '/reports/items',
    PIVOT: '/reports/pivot',
    LEDGER: '/reports/ledger',
  },
  MASTERS: {
    ROOT: '/masters/companies',
    COMPANIES: '/masters/companies',
    PORTS: '/masters/ports',
    HS_CODES: '/masters/hs-codes',
    ITEM_GROUPS: '/masters/item-groups',
    ITEM_NAMES: '/masters/item-names',
    SION_NORM_CLASSES: '/masters/sion-norm-classes',
    EXCHANGE_RATES: '/masters/exchange-rates',
  },
  TASKS: '/tasks',
  LEDGER_UPLOAD: '/ledger-upload',
  LICENSE_LEDGER: '/license-ledger',
  LICENSE_LEDGER_DETAIL: (id: string | number) => `/license-ledger/${id}`,
  INCENTIVE_LICENSES: '/incentive-licenses',
  INCENTIVE_LICENSE_NEW: '/incentive-licenses/new',
  INCENTIVE_LICENSE_EDIT: (id: string | number) => `/incentive-licenses/${id}/edit`,
  SETTINGS: '/settings',
  LOGIN: '/login',
  ADMIN: {
    USERS: '/admin/users',
    USER_NEW: '/admin/users/new',
    USER_EDIT: (id: string | number) => `/admin/users/${id}/edit`,
    ACTIVITY_LOG: '/admin/activity-log',
  },
  PROFILE: '/profile',
} as const
