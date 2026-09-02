import { createContext } from 'react'
import type { SiteRuntimeConfig } from '../lib/runtimeConfig'

export interface TurnstileRuntimeConfig {
  enabled: boolean
  siteKey: string
  scriptUrl?: string
}

export interface RuntimeConfigValue {
  loading: boolean
  turnstile: TurnstileRuntimeConfig
  features: readonly string[]
  trustedNotificationOrigins: readonly string[]
  site: SiteRuntimeConfig
}

const RuntimeConfigContext = createContext<RuntimeConfigValue | undefined>(undefined)

export { RuntimeConfigContext }
