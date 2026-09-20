import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'

export default function ComplianceAdminLayout({
  title,
  children,
  showNavigation = true,
}: {
  title: string
  children: ReactNode
  showNavigation?: boolean
}) {
  const { site } = useRuntimeConfig()
  const origin = typeof window === 'undefined' ? 'https://hemu.site' : window.location.origin

  return (
    <div className="min-h-screen flex flex-col" style={{ background: '#f5f7fa' }}>
      <header
        className="sticky top-0 z-50 text-white"
        style={{ background: '#102a56', boxShadow: '0 2px 8px rgba(0,0,0,0.16)' }}
      >
        <div className="mx-auto flex items-center justify-between gap-4 px-5" style={{ maxWidth: 1320, height: 64 }}>
          <div>
            <div className="font-bold text-base">{site.siteName} · {title}</div>
            <div className="text-xs" style={{ color: 'rgba(255,255,255,0.72)' }}>
              正式域名：{origin}
            </div>
          </div>
          {showNavigation && (
            <div className="flex items-center gap-4 text-sm">
              <Link to="/mall/admin/information" style={{ color: '#fff' }}>信息审核</Link>
              <Link to="/mall/admin/publisher-verifications" style={{ color: '#fff' }}>发布者实名</Link>
              <Link to="/mall/admin/shops" style={{ color: '#fff' }}>商家资质</Link>
              <Link to="/admin" style={{ color: '#fff' }}>审计日志</Link>
            </div>
          )}
        </div>
      </header>

      <main className="flex-1 w-full mx-auto px-5 py-5" style={{ maxWidth: 1320 }}>
        {children}
      </main>

      <footer
        className="sticky bottom-0 z-40 text-center text-xs py-2 px-4"
        style={{ color: '#536176', background: 'rgba(255,255,255,0.96)', borderTop: '1px solid #dfe5ee' }}
      >
        {site.legalEntityName || site.siteName} · {origin} · {site.icpRecordNumber}
      </footer>
    </div>
  )
}
