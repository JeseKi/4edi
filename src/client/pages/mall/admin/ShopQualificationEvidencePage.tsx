import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Alert, Button, Descriptions, Result, Spin, Table, Tag } from 'antd'
import { PrinterOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import ComplianceAdminLayout from '../../../components/mall/ComplianceAdminLayout'
import ProtectedMaterialPreview from '../../../components/mall/ProtectedMaterialPreview'
import RegulatoryEvidenceLinkPanel from '../../../components/mall/RegulatoryEvidenceLinkPanel'
import { getAdminShopDetail } from '../../../lib/sellerMall'
import type { ShopAdminDetail } from '../../../lib/types'

const STATUS: Record<string, { text: string; color: string }> = {
  pending: { text: '审核中', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
  closed: { text: '已关闭', color: 'default' },
}

const REVIEW_RESULT: Record<string, { text: string; color: string }> = {
  preapproved: { text: '核验通过', color: 'green' },
  approved: { text: '核验通过', color: 'green' },
  rejected: { text: '核验驳回', color: 'red' },
}

const AGREEMENT_STATUS: Record<string, string> = {
  generated: '已生成',
  merchant_signed: '商家已签署',
  platform_signed: '平台已签署',
  archived: '已归档',
  superseded: '已由新版本替代',
}

const formatTime = (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'

export default function ShopQualificationEvidencePage() {
  const { shopId } = useParams()
  const [data, setData] = useState<ShopAdminDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    const id = Number(shopId)
    if (!Number.isInteger(id) || id <= 0) {
      setError(true)
      setLoading(false)
      return
    }
    getAdminShopDetail(id)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [shopId])

  return (
    <ComplianceAdminLayout title="商家实名与资质监管取证">
      {loading && <div className="flex justify-center py-24"><Spin size="large" /></div>}
      {error && <Result status="error" title="商家取证记录加载失败" extra={<Link to="/mall/admin/shops">返回商家审核</Link>} />}
      {data && (() => {
        const { shop, qualification_reviews: reviews } = data
        const status = STATUS[shop.status] || { text: shop.status, color: 'default' }
        return (
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-xl font-bold mb-1">商家实名与资质取证记录 #{shop.id}</h1>
                <div className="text-sm" style={{ color: '#667085' }}>
                  页面数据来自正式后台，仅限授权管理员和监管核验人员查看。
                </div>
              </div>
              <div className="flex gap-2">
                <Link to="/mall/admin/shops"><Button>返回列表</Button></Link>
                <Button icon={<PrinterOutlined />} onClick={() => window.print()}>打印取证页</Button>
              </div>
            </div>

            <Alert
              type="warning"
              showIcon
              message="本页包含敏感个人和企业信息，截图和打印件仅可提交至本次 EDI 审核渠道，禁止另作他用。"
            />

            <RegulatoryEvidenceLinkPanel evidenceType="shop_qualification" resourceId={shop.id} />

            <div className="rounded bg-white p-5">
              <Descriptions title="商家主体与审核结论" bordered column={2} size="small">
                <Descriptions.Item label="店铺编号">{shop.id}</Descriptions.Item>
                <Descriptions.Item label="审核状态"><Tag color={status.color}>{status.text}</Tag></Descriptions.Item>
                <Descriptions.Item label="店铺名称">{shop.name}</Descriptions.Item>
                <Descriptions.Item label="店主用户 ID">{shop.owner_user_id}</Descriptions.Item>
                <Descriptions.Item label="经营者姓名">{shop.real_name || '-'}</Descriptions.Item>
                <Descriptions.Item label="身份证号">{shop.identity_number_masked || '-'}</Descriptions.Item>
                <Descriptions.Item label="企业法定全称">{shop.legal_entity_name || '-'}</Descriptions.Item>
                <Descriptions.Item label="统一社会信用代码">{shop.unified_social_credit_code || '-'}</Descriptions.Item>
                <Descriptions.Item label="法定代表人">{shop.legal_representative || '-'}</Descriptions.Item>
                <Descriptions.Item label="登记状态">{shop.registration_status || '-'}</Descriptions.Item>
                <Descriptions.Item label="注册地址" span={2}>{shop.registered_address || '-'}</Descriptions.Item>
                <Descriptions.Item label="实际经营地址" span={2}>{shop.business_address || '-'}</Descriptions.Item>
                <Descriptions.Item label="营业执照有效期">{shop.business_license_long_term ? '长期有效' : shop.business_license_valid_until || '-'}</Descriptions.Item>
                <Descriptions.Item label="最近资质核验时间">{formatTime(shop.last_qualification_checked_at)}</Descriptions.Item>
                <Descriptions.Item label="资质有效期">{shop.qualification_valid_until || '-'}</Descriptions.Item>
                <Descriptions.Item label="审核通过时间">{formatTime(shop.approved_at)}</Descriptions.Item>
                <Descriptions.Item label="首期经营范围" span={2}>
                  <Tag color={shop.special_license_not_required ? 'green' : 'red'}>
                    {shop.special_license_not_required ? '已确认不涉及专项许可行业' : '未确认'}
                  </Tag>
                </Descriptions.Item>
              </Descriptions>
            </div>

            <div className="rounded bg-white p-5">
              <h2 className="font-bold text-base mb-4">商家实名与企业资质具体材料</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {shop.business_license_asset_id
                  ? <ProtectedMaterialPreview assetId={shop.business_license_asset_id} title="营业执照" reviewScope="edi" />
                  : <Alert type="error" message="缺少营业执照材料" />}
                {shop.identity_front_asset_id
                  ? <ProtectedMaterialPreview assetId={shop.identity_front_asset_id} title="经营者身份证人像面" reviewScope="edi" />
                  : <Alert type="error" message="缺少身份证人像面材料" />}
                {shop.identity_back_asset_id
                  ? <ProtectedMaterialPreview assetId={shop.identity_back_asset_id} title="经营者身份证国徽面" reviewScope="edi" />
                  : <Alert type="error" message="缺少身份证国徽面材料" />}
              </div>
            </div>

            <div className="rounded bg-white p-5">
              <h2 className="font-bold text-base mb-4">企业资质核验记录</h2>
              <Table
                rowKey="id"
                pagination={false}
                dataSource={reviews}
                locale={{ emptyText: '暂无资质核验记录' }}
                columns={[
                  { title: '记录编号', dataIndex: 'id', width: 100 },
                  { title: '核验结果', dataIndex: 'result', render: (value: string) => {
                    const result = REVIEW_RESULT[value] || { text: value, color: 'default' }
                    return <Tag color={result.color}>{result.text}</Tag>
                  } },
                  { title: '核验来源', dataIndex: 'verification_source' },
                  { title: '登记状态', dataIndex: 'registration_status' },
                  { title: '核验时间', dataIndex: 'checked_at', render: (value: string) => formatTime(value) },
                  { title: '审核人员 ID', dataIndex: 'reviewer_user_id' },
                  { title: '驳回原因', dataIndex: 'reject_reason', render: (value: string | null) => value || '-' },
                ]}
              />
            </div>

            {shop.current_agreement && (
              <div className="rounded bg-white p-5">
                <Descriptions title="商家入驻协议记录" bordered column={2} size="small">
                  <Descriptions.Item label="协议编号">{shop.current_agreement.agreement_number}</Descriptions.Item>
                  <Descriptions.Item label="协议版本">{shop.current_agreement.document_version}</Descriptions.Item>
                  <Descriptions.Item label="签约方式">{shop.current_agreement.signature_mode === 'online_click' ? '商家在线确认' : '上传签署文件'}</Descriptions.Item>
                  <Descriptions.Item label="归档状态">{AGREEMENT_STATUS[shop.current_agreement.status] || shop.current_agreement.status}</Descriptions.Item>
                  <Descriptions.Item label="商家签约账号">{shop.current_agreement.merchant_signed_account || '-'}</Descriptions.Item>
                  <Descriptions.Item label="商家签约时间">{formatTime(shop.current_agreement.merchant_signed_at)}</Descriptions.Item>
                </Descriptions>
              </div>
            )}
          </div>
        )
      })()}
    </ComplianceAdminLayout>
  )
}
