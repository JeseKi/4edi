import { useEffect, useState } from 'react'
import { Alert, Button, Descriptions, Spin } from 'antd'
import { useParams } from 'react-router-dom'
import MarkdownContent from '../../../components/common/MarkdownContent'
import {
  getAdminShopAgreement,
  getAdminShopDetail,
  getMyMallShop,
  getMyShopAgreement,
} from '../../../lib/sellerMall'
import type { MallShop, ShopAgreement } from '../../../lib/types'

export default function ShopAgreementPrintPage() {
  const { shopId } = useParams()
  const [agreement, setAgreement] = useState<ShopAgreement | null>(null)
  const [shop, setShop] = useState<MallShop | null>(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    const load = shopId
      ? Promise.all([
        getAdminShopAgreement(Number(shopId)),
        getAdminShopDetail(Number(shopId)).then((detail) => detail.shop),
      ])
      : Promise.all([getMyShopAgreement(), getMyMallShop()])
    load.then(([nextAgreement, nextShop]) => {
      setAgreement(nextAgreement)
      setShop(nextShop)
    }).catch(() => setFailed(true))
  }, [shopId])

  if (failed) return <div className="agreement-print-shell"><Alert type="error" showIcon message="协议尚未生成或无法读取" /></div>
  if (!agreement) return <div className="agreement-print-loading"><Spin size="large" /></div>

  return (
    <div className="agreement-print-shell">
      <div className="agreement-print-actions">
        <Button type="primary" onClick={() => window.print()}>打印 / 保存为 PDF</Button>
        <span>
          {agreement.signature_mode === 'online_click'
            ? agreement.merchant_signed_at
              ? '此页面包含已归档的完整协议和电子签约凭证。'
              : '请阅读完整协议；签署操作需返回商家中心完成。'
            : '这是历史文件签署协议的正文快照。'}
        </span>
      </div>
      <article className="agreement-print-paper">
        <MarkdownContent content={agreement.content_markdown} />
        {agreement.signature_mode === 'online_click' && agreement.merchant_signed_at && shop && (
          <section className="mt-8 border-0 border-t border-solid border-gray-300 pt-6">
            <h2>电子签约凭证</h2>
            <p>以下记录由系统在店主账号主动确认签约时生成，并与上述完整协议一并归档。</p>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="商家主体">{shop.legal_entity_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="店铺名称">{shop.name}</Descriptions.Item>
              <Descriptions.Item label="店铺编号">{shop.id}</Descriptions.Item>
              <Descriptions.Item label="签约账号">
                {agreement.merchant_signed_account || `用户 #${agreement.merchant_signed_by_user_id}`}
              </Descriptions.Item>
              <Descriptions.Item label="协议编号">{agreement.agreement_number}</Descriptions.Item>
              <Descriptions.Item label="协议版本">{agreement.document_version}</Descriptions.Item>
              <Descriptions.Item label="签约方式">登录账号主动勾选并点击确认</Descriptions.Item>
              <Descriptions.Item label="签约时间">
                {new Date(agreement.merchant_signed_at).toLocaleString('zh-CN', { hour12: false })}
              </Descriptions.Item>
            </Descriptions>
          </section>
        )}
      </article>
    </div>
  )
}
