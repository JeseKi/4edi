import { useEffect, useState } from 'react'
import { Alert, Button, Spin } from 'antd'
import MarkdownContent from '../../../components/common/MarkdownContent'
import { getMyShopAgreement } from '../../../lib/sellerMall'
import type { ShopAgreement } from '../../../lib/types'

export default function ShopAgreementPrintPage() {
  const [agreement, setAgreement] = useState<ShopAgreement | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    getMyShopAgreement().then(setAgreement).catch(() => setFailed(true))
  }, [])

  if (failed) return <div className="agreement-print-shell"><Alert type="error" showIcon message="协议尚未生成或无法读取" /></div>
  if (!agreement) return <div className="agreement-print-loading"><Spin size="large" /></div>

  return (
    <div className="agreement-print-shell">
      <div className="agreement-print-actions">
        <Button type="primary" onClick={() => window.print()}>打印 / 保存为 PDF</Button>
        <span>打印后请签字或盖章，再回到商家中心上传完整文件。</span>
      </div>
      <article className="agreement-print-paper">
        <MarkdownContent content={agreement.content_markdown} />
      </article>
    </div>
  )
}
