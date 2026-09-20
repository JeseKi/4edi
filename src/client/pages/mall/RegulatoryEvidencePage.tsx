import { useEffect, useMemo, useState } from 'react'
import { Alert, Descriptions, Result, Spin, Table, Tag } from 'antd'
import dayjs from 'dayjs'
import ComplianceAdminLayout from '../../components/mall/ComplianceAdminLayout'
import ProtectedMaterialPreview from '../../components/mall/ProtectedMaterialPreview'
import InformationEvidenceRecords from '../../components/mall/InformationEvidenceRecords'
import { getRegulatoryEvidence } from '../../lib/regulatoryEvidence'
import type { RegulatoryEvidence } from '../../lib/types'

const STATUS: Record<string, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
  closed: { text: '已关闭', color: 'default' },
}

const REVIEW_RESULT: Record<string, { text: string; color: string }> = {
  preapproved: { text: '核验通过', color: 'green' },
  approved: { text: '核验通过', color: 'green' },
  rejected: { text: '核验驳回', color: 'red' },
}

const DOCUMENT_TYPES: Record<string, string> = {
  resident_identity_card: '居民身份证',
  passport: '护照',
}

const formatTime = (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'

export default function RegulatoryEvidencePage() {
  const token = useMemo(() => window.location.hash.slice(1), [])
  const [data, setData] = useState<RegulatoryEvidence | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    document.title = '监管核验材料'
    const robots = document.createElement('meta')
    robots.name = 'robots'
    robots.content = 'noindex,nofollow,noarchive'
    document.head.appendChild(robots)
    if (!/^[A-Za-z0-9]{32}$/.test(token)) {
      setError(true)
      setLoading(false)
      return () => robots.remove()
    }
    getRegulatoryEvidence(token)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
    return () => robots.remove()
  }, [token])

  return (
    <ComplianceAdminLayout title="监管核验材料" showNavigation={false}>
      {loading && <div className="flex justify-center py-24"><Spin size="large" /></div>}
      {error && <Result status="warning" title="核验链接不存在或已失效" subTitle="请联系平台管理员重新生成监管核验链接。" />}
      {data?.publisher_verification && (() => {
        const { verification: item, posts } = data.publisher_verification
        const currentStatus = STATUS[item.status]
        return (
          <div className="space-y-5">
            <h1 className="text-xl font-bold">发布者实名认证监管核验记录 #{item.id}</h1>
            <Alert type="warning" showIcon message="本页包含敏感个人信息，仅限本次 EDI 监管审核使用；平台可随时吊销本链接。" />
            <div className="rounded bg-white p-5">
              <Descriptions title="实名审核结论" bordered column={2} size="small">
                <Descriptions.Item label="实名记录编号">{item.id}</Descriptions.Item>
                <Descriptions.Item label="审核状态"><Tag color={currentStatus.color}>{currentStatus.text}</Tag></Descriptions.Item>
                <Descriptions.Item label="用户账号">{item.username}（用户 ID {item.user_id}）</Descriptions.Item>
                <Descriptions.Item label="真实姓名">{item.real_name}</Descriptions.Item>
                <Descriptions.Item label="证件类型">{DOCUMENT_TYPES[item.document_type] || item.document_type}</Descriptions.Item>
                <Descriptions.Item label="证件号码">{item.document_number_masked}</Descriptions.Item>
                <Descriptions.Item label="证件有效期">{item.document_long_term ? '长期有效' : item.document_valid_until || '-'}</Descriptions.Item>
                <Descriptions.Item label="当前有效性">{item.is_currently_valid ? <Tag color="green">有效</Tag> : <Tag color="red">无效</Tag>}</Descriptions.Item>
                <Descriptions.Item label="提交时间">{formatTime(item.submitted_at)}</Descriptions.Item>
                <Descriptions.Item label="审核时间">{formatTime(item.reviewed_at)}</Descriptions.Item>
                <Descriptions.Item label="审核人员">{item.reviewer_username || '-'}{item.reviewer_user_id ? `（ID ${item.reviewer_user_id}）` : ''}</Descriptions.Item>
                <Descriptions.Item label="核验方式">平台人工核验身份证明原件</Descriptions.Item>
                <Descriptions.Item label="驳回原因" span={2}>{item.reject_reason || '-'}</Descriptions.Item>
              </Descriptions>
            </div>
            <div className="rounded bg-white p-5">
              <h2 className="font-bold text-base mb-4">实名认证具体材料</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <ProtectedMaterialPreview assetId={item.document_front_asset_id} title="身份证人像面 / 证件首页" regulatoryToken={token} />
                {item.document_back_asset_id
                  ? <ProtectedMaterialPreview assetId={item.document_back_asset_id} title="身份证国徽面 / 证件背面" regulatoryToken={token} />
                  : <Alert type="info" message="该证件无背面材料" />}
              </div>
            </div>
            <div className="rounded bg-white p-5">
              <h2 className="font-bold text-base mb-4">关联信息发布审核记录</h2>
              <InformationEvidenceRecords posts={posts} pageSize={false} />
            </div>
          </div>
        )
      })()}
      {data?.shop_qualification && (() => {
        const { shop, qualification_reviews: reviews } = data.shop_qualification
        const currentStatus = STATUS[shop.status] || { text: shop.status, color: 'default' }
        return (
          <div className="space-y-5">
            <h1 className="text-xl font-bold">商家实名与资质监管核验记录 #{shop.id}</h1>
            <Alert type="warning" showIcon message="本页包含敏感个人和企业信息，仅限本次 EDI 监管审核使用；平台可随时吊销本链接。" />
            <div className="rounded bg-white p-5">
              <Descriptions title="商家主体与审核结论" bordered column={2} size="small">
                <Descriptions.Item label="店铺编号">{shop.id}</Descriptions.Item>
                <Descriptions.Item label="审核状态"><Tag color={currentStatus.color}>{currentStatus.text}</Tag></Descriptions.Item>
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
              </Descriptions>
            </div>
            <div className="rounded bg-white p-5">
              <h2 className="font-bold text-base mb-4">商家实名与企业资质具体材料</h2>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {shop.business_license_asset_id
                  ? <ProtectedMaterialPreview assetId={shop.business_license_asset_id} title="营业执照" regulatoryToken={token} />
                  : <Alert type="error" message="缺少营业执照材料" />}
                {shop.identity_front_asset_id
                  ? <ProtectedMaterialPreview assetId={shop.identity_front_asset_id} title="经营者身份证人像面" regulatoryToken={token} />
                  : <Alert type="error" message="缺少身份证人像面材料" />}
                {shop.identity_back_asset_id
                  ? <ProtectedMaterialPreview assetId={shop.identity_back_asset_id} title="经营者身份证国徽面" regulatoryToken={token} />
                  : <Alert type="error" message="缺少身份证国徽面材料" />}
              </div>
            </div>
            <div className="rounded bg-white p-5">
              <h2 className="font-bold text-base mb-4">企业资质核验记录</h2>
              <Table rowKey="id" pagination={false} dataSource={reviews} locale={{ emptyText: '暂无资质核验记录' }} columns={[
                { title: '记录编号', dataIndex: 'id', width: 100 },
                { title: '核验结果', dataIndex: 'result', render: (value: string) => {
                  const result = REVIEW_RESULT[value] || { text: value, color: 'default' }
                  return <Tag color={result.color}>{result.text}</Tag>
                } },
                { title: '核验来源', dataIndex: 'verification_source' },
                { title: '登记状态', dataIndex: 'registration_status' },
                { title: '核验时间', dataIndex: 'checked_at', render: formatTime },
                { title: '审核人员 ID', dataIndex: 'reviewer_user_id' },
                { title: '驳回原因', dataIndex: 'reject_reason', render: (value: string | null) => value || '-' },
              ]} />
            </div>
          </div>
        )
      })()}
    </ComplianceAdminLayout>
  )
}
