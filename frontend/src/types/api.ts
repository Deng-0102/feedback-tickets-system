export type Role = 'USER' | 'AGENT' | 'ADMIN'

export interface ApiEnvelope<T> {
  code: number
  message: string
  data: T
}

export interface UserProfile {
  id: number
  username: string
  display_name: string
  role: Role
  is_active: boolean
}

export interface LoginPayload {
  username: string
  password: string
}

export interface LoginResult {
  access_token: string
  token_type: 'bearer' | string
  user: UserProfile
}

export interface ApiErrorData {
  code?: number
  message?: string
  detail?: string
}
