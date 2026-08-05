import api from './api'

export interface FrontendConfigResponse {
  features: string[]
  turnstile?: {
    enabled?: boolean
    site_key?: string
    script_url?: string
  }
  notifications?: { trusted_external_origins?: string[] }
}

export async function fetchFrontendConfig(): Promise<FrontendConfigResponse | null> {
  try {
    const response = await api.get<FrontendConfigResponse>('/frontend-config')
    return response.data
  } catch {
    return null
  }
}
