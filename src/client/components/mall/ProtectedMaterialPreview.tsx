import { useEffect, useState } from 'react'
import { Alert, Image, Spin } from 'antd'
import api from '../../lib/api'

const WATERMARKS = {
  icp: '仅用于本次 ICP 信息发布审核 · 其他用途无效',
  edi: '仅用于本次 EDI 实名认证审核 · 其他用途无效',
} as const

export default function ProtectedMaterialPreview({
  assetId,
  title,
  regulatoryToken,
  reviewScope,
}: {
  assetId: string
  title: string
  regulatoryToken?: string
  reviewScope: keyof typeof WATERMARKS
}) {
  const [preview, setPreview] = useState<{ url: string; contentType: string } | null>(null)
  const [error, setError] = useState(false)

  useEffect(() => {
    let alive = true
    let objectUrl: string | null = null
    setPreview(null)
    setError(false)
    const url = regulatoryToken
      ? `/regulatory-evidence/assets/${assetId}`
      : `/files/${assetId}/download`
    void api.get<Blob>(url, {
      responseType: 'blob',
      headers: regulatoryToken
        ? { 'X-Regulatory-Evidence-Token': regulatoryToken }
        : undefined,
    })
      .then((downloadResponse) => {
        if (!alive) return
        objectUrl = URL.createObjectURL(downloadResponse.data)
        setPreview({
          url: objectUrl,
          contentType: downloadResponse.data.type,
        })
      })
      .catch(() => {
        if (alive) setError(true)
      })

    return () => {
      alive = false
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [assetId, regulatoryToken])

  return (
    <section>
      <div className="font-medium mb-2">{title}</div>
      <div
        className="relative overflow-hidden rounded border bg-white flex items-center justify-center"
        style={{ minHeight: 260 }}
      >
        {!preview && !error && <Spin />}
        {error && <Alert type="error" showIcon message="材料加载失败或无查看权限" />}
        {preview && preview.contentType === 'application/pdf' && (
          <iframe title={title} src={preview.url} style={{ width: '100%', height: 420, border: 0 }} />
        )}
        {preview && preview.contentType !== 'application/pdf' && (
          <Image src={preview.url} alt={title} style={{ maxHeight: 420, objectFit: 'contain' }} />
        )}
        {preview && (
          <div
            aria-hidden="true"
            className="absolute inset-0 flex flex-col items-center justify-around pointer-events-none overflow-hidden"
            style={{ color: 'rgba(180, 0, 0, 0.28)', fontWeight: 700 }}
          >
            {[0, 1, 2].map((index) => (
              <div
                key={index}
                style={{ transform: 'rotate(-18deg)', whiteSpace: 'nowrap', fontSize: 18 }}
              >
                {WATERMARKS[reviewScope]}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
