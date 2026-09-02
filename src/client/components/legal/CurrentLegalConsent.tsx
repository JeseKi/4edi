import { useEffect, useState } from 'react'
import { Alert, Button, Checkbox, Space } from 'antd'
import {
  acceptCurrentLegalDocuments,
  getMyLegalAcceptanceStatus,
} from '../../lib/legal'
import { resolveApiErrorMessage } from '../../lib/error'

export default function CurrentLegalConsent({ onReady }: { onReady?: () => void }) {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof getMyLegalAcceptanceStatus>> | null>(null)
  const [userChecked, setUserChecked] = useState(false)
  const [privacyChecked, setPrivacyChecked] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getMyLegalAcceptanceStatus()
      .then((value) => {
        setStatus(value)
        if (value.all_current_accepted) onReady?.()
      })
      .catch((err) => setError(resolveApiErrorMessage(err, '协议确认状态加载失败')))
  }, [onReady])

  if (status?.all_current_accepted) return null

  const accept = async () => {
    if (!status || !userChecked || !privacyChecked) return
    setSaving(true)
    setError(null)
    try {
      const updated = await acceptCurrentLegalDocuments({
        user_agreement_version: status.user_agreement_version,
        privacy_policy_version: status.privacy_policy_version,
      })
      setStatus(updated)
      onReady?.()
    } catch (err) {
      setError(resolveApiErrorMessage(err, '协议确认失败'))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Alert
      type="warning"
      showIcon
      message="继续使用发布或开店功能前，请确认当前协议"
      description={
        <Space direction="vertical" className="mt-2">
          <Checkbox checked={userChecked} onChange={(event) => setUserChecked(event.target.checked)}>
            我已阅读并同意 <a href="/legal/user-agreement" target="_blank" rel="noreferrer">《用户服务协议》</a>
          </Checkbox>
          <Checkbox checked={privacyChecked} onChange={(event) => setPrivacyChecked(event.target.checked)}>
            我已阅读并同意 <a href="/legal/privacy-policy" target="_blank" rel="noreferrer">《隐私政策》</a>
          </Checkbox>
          {error && <span style={{ color: '#cf1322' }}>{error}</span>}
          <Button type="primary" disabled={!userChecked || !privacyChecked || !status} loading={saving} onClick={() => void accept()}>
            确认当前版本
          </Button>
        </Space>
      }
    />
  )
}
