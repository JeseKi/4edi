import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Alert, Button, Descriptions, Result, Spin, Tag } from 'antd'
import { PrinterOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import ComplianceAdminLayout from '../../../components/mall/ComplianceAdminLayout'
import ProtectedMaterialPreview from '../../../components/mall/ProtectedMaterialPreview'
import RegulatoryEvidenceLinkPanel from '../../../components/mall/RegulatoryEvidenceLinkPanel'
import InformationEvidenceRecords from '../../../components/mall/InformationEvidenceRecords'
import { adminGetPublisherVerificationEvidence } from '../../../lib/information'
import type { PublisherVerificationEvidence } from '../../../lib/types'

const STATUS: Record<string, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
}

const DOCUMENT_TYPES: Record<string, string> = {
  resident_identity_card: '居民身份证',
  passport: '护照',
}

const formatTime = (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'

export default function PublisherVerificationEvidencePage() {
  const { verificationId } = useParams()
  const [data, setData] = useState<PublisherVerificationEvidence | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    const id = Number(verificationId)
    if (!Number.isInteger(id) || id <= 0) {
      setError(true)
      setLoading(false)
      return
    }
    adminGetPublisherVerificationEvidence(id)
      .then(setData)
      .catch(() => setError(true))
      .finally(() => setLoading(false))
  }, [verificationId])

  return (
    <ComplianceAdminLayout title="发布者实名认证监管取证">
      {loading && <div className="flex justify-center py-24"><Spin size="large" /></div>}
      {error && <Result status="error" title="实名取证记录加载失败" extra={<Link to="/mall/admin/publisher-verifications">返回实名审核</Link>} />}
      {data && (() => {
        const item = data.verification
        const status = STATUS[item.status]
        return (
          <div className="space-y-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h1 className="text-xl font-bold mb-1">实名认证取证记录 #{item.id}</h1>
                <div className="text-sm" style={{ color: '#667085' }}>
                  页面数据来自正式后台，仅限授权管理员和监管核验人员查看。
                </div>
              </div>
              <div className="flex gap-2">
                <Link to="/mall/admin/publisher-verifications"><Button>返回列表</Button></Link>
                <Button icon={<PrinterOutlined />} onClick={() => window.print()}>打印取证页</Button>
              </div>
            </div>

            <Alert
              type="warning"
              showIcon
              message="本页包含敏感个人信息，截图和打印件仅可提交至本次 ICP 信息发布审核渠道，禁止另作他用。"
            />

            <RegulatoryEvidenceLinkPanel evidenceType="publisher_verification" resourceId={item.id} />

            <div className="rounded bg-white p-5">
              <Descriptions title="实名审核结论" bordered column={2} size="small">
                <Descriptions.Item label="实名记录编号">{item.id}</Descriptions.Item>
                <Descriptions.Item label="审核状态"><Tag color={status.color}>{status.text}</Tag></Descriptions.Item>
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
                <ProtectedMaterialPreview assetId={item.document_front_asset_id} title="身份证人像面 / 证件首页" reviewScope="icp" />
                {item.document_back_asset_id
                  ? <ProtectedMaterialPreview assetId={item.document_back_asset_id} title="身份证国徽面 / 证件背面" reviewScope="icp" />
                  : <Alert type="info" message="该证件无背面材料" />}
              </div>
            </div>

            <div className="rounded bg-white p-5">
              <h2 className="font-bold text-base mb-4">关联信息发布审核记录</h2>
              <InformationEvidenceRecords posts={data.posts} />
            </div>
          </div>
        )
      })()}
    </ComplianceAdminLayout>
  )
}
