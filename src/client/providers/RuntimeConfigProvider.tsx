import { type ReactNode, useEffect, useMemo, useState } from 'react'
import {
  RuntimeConfigContext,
  type RuntimeConfigValue,
  type TurnstileRuntimeConfig,
} from '../contexts/RuntimeConfigContext'
import { fetchFrontendConfig } from '../lib/runtimeConfig'
import type { SiteRuntimeConfig } from '../lib/runtimeConfig'

const fallbackTurnstileConfig: TurnstileRuntimeConfig = {
  enabled: Boolean((import.meta.env.VITE_TURNSTILE_SITE_KEY ?? '').trim()),
  siteKey: (import.meta.env.VITE_TURNSTILE_SITE_KEY ?? '').trim(),
}

const fallbackSiteConfig: SiteRuntimeConfig = {
  siteName: '沐泽健康',
  legalEntityName: '',
  registeredAddress: '',
  serviceEmail: '',
  icpRecordNumber: '',
  configurationComplete: false,
}

export function RuntimeConfigProvider({ children }: { children: ReactNode }) {
  const [loading, setLoading] = useState(true)
  const [turnstile, setTurnstile] = useState<TurnstileRuntimeConfig>(fallbackTurnstileConfig)
  const [features, setFeatures] = useState<string[]>([])
  const [trustedNotificationOrigins, setTrustedNotificationOrigins] = useState<string[]>([])
  const [site, setSite] = useState<SiteRuntimeConfig>(fallbackSiteConfig)

  useEffect(() => {
    let alive = true

    const load = async () => {
      try {
        const config = await fetchFrontendConfig()
        if (alive) {
          setFeatures(config?.features ?? [])
          setTrustedNotificationOrigins(config?.notifications?.trusted_external_origins ?? [])
          const rawSite = config?.site
          setSite({
            siteName: rawSite?.site_name ?? fallbackSiteConfig.siteName,
            legalEntityName: rawSite?.legal_entity_name ?? '',
            registeredAddress: rawSite?.registered_address ?? '',
            serviceEmail: rawSite?.service_email ?? '',
            icpRecordNumber: rawSite?.icp_record_number ?? '',
            configurationComplete: rawSite?.configuration_complete ?? false,
          })
        }
        const devTurnstile = config?.turnstile
        if (!alive || !devTurnstile) {
          return
        }

        const siteKey = (devTurnstile.site_key ?? '').trim() || fallbackTurnstileConfig.siteKey
        const scriptUrl = (devTurnstile.script_url ?? '').trim() || undefined
        setTurnstile({
          enabled: Boolean(devTurnstile.enabled && siteKey),
          siteKey,
          scriptUrl,
        })
      } finally {
        if (alive) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      alive = false
    }
  }, [])

  const value = useMemo<RuntimeConfigValue>(
    () => ({
      loading,
      turnstile,
      features,
      trustedNotificationOrigins,
      site,
    }),
    [features, loading, site, trustedNotificationOrigins, turnstile],
  )

  return (
    <RuntimeConfigContext.Provider value={value}>
      {children}
    </RuntimeConfigContext.Provider>
  )
}
