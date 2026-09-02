import { useCallback, useEffect, useState } from 'react'
import { App, Button, Descriptions, Drawer, Form, Input, Modal, Table, Tabs, Tag } from 'antd'
import dayjs from 'dayjs'
import api from '../../../lib/api'
import {
  adminListPublisherVerifications,
  adminReviewPublisherVerification,
} from '../../../lib/information'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { PublisherVerification, PublisherVerificationStatus } from '../../../lib/types'

const LABELS: Record<PublisherVerificationStatus, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
}

export default function PublisherVerificationAdminPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [status, setStatus] = useState<PublisherVerificationStatus | ''>('pending')
  const [items, setItems] = useState<PublisherVerification[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<PublisherVerification | null>(null)
  const [review, setReview] = useState<{ item: PublisherVerification; approved: boolean } | null>(null)
  const [saving, setSaving] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    adminListPublisherVerifications({ status: status || undefined, page, page_size: 10 })
      .then((result) => { setItems(result.items); setTotal(result.total) })
      .catch((err) => message.error(resolveApiErrorMessage(err, '实名审核列表加载失败')))
      .finally(() => setLoading(false))
  }, [message, page, status])
  useEffect(load, [load])

  const submit = async () => {
    if (!review) return
    const values = await form.validateFields()
    setSaving(true)
    try {
      await adminReviewPublisherVerification(review.item.id, {
        approved: review.approved,
        reject_reason: review.approved ? undefined : values.reject_reason,
      })
      message.success(review.approved ? '实名核验已通过' : '实名核验已驳回')
      setReview(null)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '审核失败'))
    } finally {
      setSaving(false)
    }
  }

  const openMaterial = async (assetId: string) => {
    try {
      const response = await api.get<Blob>(`/files/${assetId}/download`, { responseType: 'blob' })
      window.open(URL.createObjectURL(response.data), '_blank', 'noopener,noreferrer')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '材料加载失败'))
    }
  }

  return (
    <div className="rounded bg-white p-5">
      <h3 className="text-base font-bold mb-3">发布者实名审核</h3>
      <Tabs activeKey={status} onChange={(key) => { setStatus(key as PublisherVerificationStatus | ''); setPage(1) }} items={[...Object.entries(LABELS).map(([key, value]) => ({ key, label: value.text })), { key: '', label: '全部' }]} />
      <Table rowKey="id" loading={loading} dataSource={items} pagination={{ current: page, pageSize: 10, total, onChange: setPage }} columns={[
        { title: '编号', dataIndex: 'id' },
        { title: '账号', dataIndex: 'username' },
        { title: '真实姓名', dataIndex: 'real_name' },
        { title: '证件号码', dataIndex: 'document_number_masked' },
        { title: '提交时间', dataIndex: 'submitted_at', render: (value: string) => dayjs(value).format('YYYY-MM-DD HH:mm') },
        { title: '状态', dataIndex: 'status', render: (value: PublisherVerificationStatus) => <Tag color={LABELS[value].color}>{LABELS[value].text}</Tag> },
        { title: '操作', render: (_: unknown, item: PublisherVerification) => <div className="flex gap-1"><Button size="small" onClick={() => setDetail(item)}>详情</Button>{item.status === 'pending' && <><Button type="primary" size="small" onClick={() => setReview({ item, approved: true })}>通过</Button><Button danger size="small" onClick={() => setReview({ item, approved: false })}>驳回</Button></>}</div> },
      ]} />
      <Drawer title="实名申请详情" open={Boolean(detail)} onClose={() => setDetail(null)}>
        {detail && <Descriptions column={1} bordered size="small">
          <Descriptions.Item label="账号">{detail.username}</Descriptions.Item>
          <Descriptions.Item label="真实姓名">{detail.real_name}</Descriptions.Item>
          <Descriptions.Item label="证件号码">{detail.document_number_masked}</Descriptions.Item>
          <Descriptions.Item label="有效期">{detail.document_long_term ? '长期' : detail.document_valid_until}</Descriptions.Item>
          <Descriptions.Item label="材料"><Button size="small" onClick={() => void openMaterial(detail.document_front_asset_id)}>正面/首页</Button>{detail.document_back_asset_id && <Button className="ml-2" size="small" onClick={() => void openMaterial(detail.document_back_asset_id!)}>背面</Button>}</Descriptions.Item>
          <Descriptions.Item label="驳回原因">{detail.reject_reason || '-'}</Descriptions.Item>
        </Descriptions>}
      </Drawer>
      <Modal title={review?.approved ? '通过实名核验' : '驳回实名核验'} open={Boolean(review)} onCancel={() => setReview(null)} onOk={() => void submit()} confirmLoading={saving}>
        {!review?.approved && <Form form={form} layout="vertical"><Form.Item name="reject_reason" label="驳回原因" rules={[{ required: true, message: '请填写驳回原因' }]}><Input.TextArea maxLength={300} /></Form.Item></Form>}
      </Modal>
    </div>
  )
}
