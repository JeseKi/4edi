import { useEffect, useState } from 'react'
import { Button, Card, Result, Spin, Typography } from 'antd'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import MarkdownContent from '../../components/common/MarkdownContent'
import {
  getLegalDocument,
  type LegalDocument,
  type LegalDocumentType,
} from '../../lib/legal'

const PATH_TYPES: Record<string, LegalDocumentType> = {
  'user-agreement': 'user_agreement',
  'privacy-policy': 'privacy_policy',
  'merchant-agreement': 'merchant_agreement',
}

export default function LegalDocumentPage() {
  const { documentKey = '' } = useParams()
  const [searchParams] = useSearchParams()
  const [document, setDocument] = useState<LegalDocument | null>(null)
  const [failed, setFailed] = useState(false)
  const documentType = PATH_TYPES[documentKey]
  const version = searchParams.get('version') || undefined

  useEffect(() => {
    if (!documentType) {
      setFailed(true)
      return
    }
    setFailed(false)
    getLegalDocument(documentType, version)
      .then(setDocument)
      .catch(() => setFailed(true))
  }, [documentType, version])

  if (failed) {
    return (
      <Result
        status="404"
        title="协议版本不存在"
        extra={<Link to="/"><Button type="primary">返回首页</Button></Link>}
      />
    )
  }
  if (!document) {
    return <div className="flex justify-center py-24"><Spin size="large" /></div>
  }
  return (
    <main className="mx-auto px-4 py-8" style={{ maxWidth: 920 }}>
      <Card>
        <Typography.Title level={2}>{document.title}</Typography.Title>
        <Typography.Text type="secondary">
          版本：{document.version} · 生效日期：{document.effective_at}
        </Typography.Text>
        <div className="mt-6">
          <MarkdownContent content={document.content_markdown} />
        </div>
      </Card>
    </main>
  )
}
