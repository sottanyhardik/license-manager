// accounts/types.ts
// Types for the user administration feature.

export interface ManagedUser {
  id: number
  username: string
  email: string | null
  first_name: string
  last_name: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  roles: string[]
  date_joined: string
  last_login: string | null
}

export interface UserFormValues {
  username: string
  email: string
  first_name: string
  last_name: string
  /** Only sent on create, or omitted on edit when unchanged. */
  password?: string
  is_active: boolean
  is_staff: boolean
  is_superuser: boolean
  roles: string[]
}
