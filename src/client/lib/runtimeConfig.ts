import api from './api'

export interface FrontendConfigResponse {
  features: string[]
  turnstile?: {
    enabled?: boolean
    site_key?: string
    script_url?: string
  }
  notifications?: { trusted_external_origins?: string[] }
  site?: {
    site_name?: string
    legal_entity_name?: string
    registered_address?: string
    service_email?: string
    icp_record_number?: string
    configuration_complete?: boolean
  }
}

export interface SiteRuntimeConfig {
  siteName: string
  legalEntityName: string
  registeredAddress: string
  serviceEmail: string
  icpRecordNumber: string
  configurationComplete: boolean
}

export async function fetchFrontendConfig(): Promise<FrontendConfigResponse | null> {
  try {
    const response = await api.get<FrontendConfigResponse>('/frontend-config')
    return response.data
  } catch {
    return null
  }
}
