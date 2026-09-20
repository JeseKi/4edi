import { useCallback, useEffect, useState } from 'react'
import { App, Button, Descriptions, Input, Popconfirm, Space, Table, Tag } from 'antd'
import dayjs from 'dayjs'
import {
  createRegulatoryEvidenceLink,
  listRegulatoryEvidenceLinks,
  revokeRegulatoryEvidenceLink,
} from '../../lib/regulatoryEvidence'
import type { RegulatoryEvidenceLink, RegulatoryEvidenceType } from '../../lib/types'

const formatTime = (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'

export default function RegulatoryEvidenceLinkPanel({
  evidenceType,
  resourceId,
}: {
  evidenceType: RegulatoryEvidenceType
  resourceId: number
}) {
  const { message } = App.useApp()
  const [links, setLinks] = useState<RegulatoryEvidenceLink[]>([])
  const [createdUrl, setCreatedUrl] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    try {
      setLinks(await listRegulatoryEvidenceLinks(evidenceType, resourceId))
    } catch {
      message.error('监管核验链接加载失败')
    }
  }, [evidenceType, resourceId, message])

  useEffect(() => { void load() }, [load])

  const create = async () => {
    setLoading(true)
    try {
      const created = await createRegulatoryEvidenceLink(evidenceType, resourceId)
      setCreatedUrl(`${window.location.origin}${created.share_path}`)
      await load()
      message.success('已生成不限时监管核验链接；完整链接仅在本次显示')
    } catch {
      message.error('监管核验链接生成失败')
    } finally {
      setLoading(false)
    }
  }

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(createdUrl)
      message.success('链接已复制')
    } catch {
      message.error('复制失败，请手动选择并复制')
    }
  }

  const revoke = async (linkId: number) => {
    try {
      await revokeRegulatoryEvidenceLink(linkId)
      if (createdUrl) setCreatedUrl('')
      await load()
      message.success('监管核验链接已吊销')
    } catch {
      message.error('吊销失败')
    }
  }

  return (
    <div className="rounded bg-white p-5">
      <div className="flex items-start justify-between gap-4 mb-4">
        <div>
          <h2 className="font-bold text-base mb-1">监管核验链接</h2>
          <div className="text-sm" style={{ color: '#667085' }}>
            审核人员无需管理员账号。链接不限时、仅能查看本条材料，并可随时吊销。
          </div>
        </div>
        <Button type="primary" loading={loading} onClick={() => void create()}>
          生成 32 位核验链接
        </Button>
      </div>

      {createdUrl && (
        <Descriptions bordered size="small" column={1} className="mb-4">
          <Descriptions.Item label="本次生成的完整链接">
            <Space.Compact style={{ width: '100%' }}>
              <Input value={createdUrl} readOnly />
              <Button onClick={() => void copy()}>复制</Button>
            </Space.Compact>
          </Descriptions.Item>
        </Descriptions>
      )}

      <Table
        rowKey="id"
        size="small"
        pagination={false}
        dataSource={links}
        locale={{ emptyText: '尚未生成监管核验链接' }}
        columns={[
          { title: '链接编号', dataIndex: 'id', width: 90 },
          { title: '令牌标识', dataIndex: 'token_hint', render: (value: string) => `末六位 ${value}` },
          { title: '生成时间', dataIndex: 'created_at', render: formatTime },
          { title: '最近查看', dataIndex: 'last_accessed_at', render: formatTime },
          { title: '查看次数', dataIndex: 'access_count', width: 90 },
          { title: '状态', render: (_: unknown, link: RegulatoryEvidenceLink) => link.revoked_at
            ? <Tag>已吊销</Tag>
            : <Tag color="green">有效（不限时）</Tag> },
          { title: '操作', render: (_: unknown, link: RegulatoryEvidenceLink) => link.revoked_at
            ? '-'
            : (
              <Popconfirm title="吊销后该链接将立即无法访问，确定吊销？" onConfirm={() => void revoke(link.id)}>
                <Button danger size="small">吊销</Button>
              </Popconfirm>
            ) },
        ]}
      />
    </div>
  )
}
