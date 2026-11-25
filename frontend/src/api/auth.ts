import { http } from './http'
import type { ApiEnvelope, LoginPayload, LoginResult, UserProfile } from '@/types/api'

export const authApi = {
  async login(payload: LoginPayload): Promise<LoginResult> {
    const response = await http.post<ApiEnvelope<LoginResult>>('/auth/login', payload)
    return response.data.data
  },

  async me(): Promise<UserProfile> {
    const response = await http.get<ApiEnvelope<UserProfile>>('/auth/me')
    return response.data.data
  },
}
