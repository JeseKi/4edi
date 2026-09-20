import { useState } from 'react'
import { Button, Descriptions, Modal, Table, Tag, Typography } from 'antd'
import dayjs from 'dayjs'
import type { InformationEvidencePost } from '../../lib/types'

const STATUS: Record<string, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
}

const formatTime = (value: string | null) => value ? dayjs(value).format('YYYY-MM-DD HH:mm:ss') : '-'

const reviewOpinion = (post: InformationEvidencePost) => {
  if (post.reject_reason) return post.reject_reason
  if (post.status === 'approved') return '审核通过'
  if (post.status === 'pending') return '等待平台审核'
  return '-'
}

export default function InformationEvidenceRecords({
  posts,
  pageSize = 5,
}: {
  posts: InformationEvidencePost[]
  pageSize?: number | false
}) {
  const [selected, setSelected] = useState<InformationEvidencePost | null>(null)

  return (
    <>
      <Table
        rowKey="id"
        pagination={pageSize === false ? false : { pageSize, showSizeChanger: false }}
        dataSource={posts}
        columns={[
          { title: '信息编号', dataIndex: 'id', width: 100 },
          { title: '标题', dataIndex: 'title' },
          { title: '提交时间', dataIndex: 'created_at', render: formatTime },
          { title: '审核时间', dataIndex: 'reviewed_at', render: formatTime },
          { title: '状态', dataIndex: 'status', render: (value: string) => <Tag color={STATUS[value]?.color}>{STATUS[value]?.text || value}</Tag> },
          { title: '审核意见', render: (_: unknown, post: InformationEvidencePost) => reviewOpinion(post) },
          { title: '操作', width: 100, render: (_: unknown, post: InformationEvidencePost) => <Button type="link" onClick={() => setSelected(post)}>查看详情</Button> },
        ]}
      />

      <Modal
        title={selected ? `信息发布详情 #${selected.id}` : '信息发布详情'}
        open={Boolean(selected)}
        width={820}
        footer={<Button onClick={() => setSelected(null)}>关闭</Button>}
        onCancel={() => setSelected(null)}
      >
        {selected && (
          <div className="space-y-4">
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="信息标题" span={2}>{selected.title}</Descriptions.Item>
              <Descriptions.Item label="所属分类">{selected.category_name}</Descriptions.Item>
              <Descriptions.Item label="价格/报价">{selected.price || '-'}</Descriptions.Item>
              <Descriptions.Item label="联系人">{selected.contact_name}</Descriptions.Item>
              <Descriptions.Item label="联系电话">{selected.contact_phone || '-'}</Descriptions.Item>
              <Descriptions.Item label="提交时间">{formatTime(selected.created_at)}</Descriptions.Item>
              <Descriptions.Item label="审核时间">{formatTime(selected.reviewed_at)}</Descriptions.Item>
              <Descriptions.Item label="审核状态">
                <Tag color={STATUS[selected.status]?.color}>{STATUS[selected.status]?.text || selected.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="审核人员 ID">{selected.reviewed_by_user_id || '-'}</Descriptions.Item>
              <Descriptions.Item label="审核意见" span={2}>{reviewOpinion(selected)}</Descriptions.Item>
            </Descriptions>

            <div className="rounded border p-4">
              <div className="font-medium mb-2">发布正文</div>
              <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>
                {selected.content}
              </Typography.Paragraph>
            </div>

            {selected.attributes && Object.keys(selected.attributes).length > 0 && (
              <Descriptions title="分类附加信息" bordered column={2} size="small">
                {Object.entries(selected.attributes).map(([key, value]) => (
                  <Descriptions.Item key={key} label={key}>{value}</Descriptions.Item>
                ))}
              </Descriptions>
            )}
          </div>
        )}
      </Modal>
    </>
  )
}
