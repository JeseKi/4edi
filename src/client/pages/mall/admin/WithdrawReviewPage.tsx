import { useCallback, useEffect, useState } from 'react'
import { App, Button, Form, Input, Modal, Table, Tabs, Tag } from 'antd'
import { handleAdminWithdraw, listAdminWithdrawals } from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import { formatFen } from '../../../lib/mallFormat'
import type { MallWithdraw, MallWithdrawStatus } from '../../../lib/types'

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '处理中', color: 'orange' },
  approved: { text: '已通过', color: 'blue' },
  rejected: { text: '已驳回', color: 'red' },
  paid: { text: '已打款', color: 'green' },
}

const TABS = [
  { key: 'pending', label: '待处理' },
  { key: 'paid', label: '已打款' },
  { key: 'rejected', label: '已驳回' },
  { key: '', label: '全部' },
]

export default function WithdrawReviewPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [status, setStatus] = useState<MallWithdrawStatus | ''>('pending')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<MallWithdraw[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [target, setTarget] = useState<MallWithdraw | null>(null)
  const [approved, setApproved] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listAdminWithdrawals({ status: status || undefined, page, page_size: 10 })
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '提现列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [status, page, message])

  useEffect(() => {
    setPage(1)
  }, [status])

  useEffect(() => {
    load()
  }, [load])

  const submit = async () => {
    if (!target) return
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await handleAdminWithdraw(target.id, {
        approved,
        reject_reason: approved ? undefined : values.reject_reason,
      })
      message.success(approved ? '已标记打款' : '已驳回，金额退回商家余额')
      setTarget(null)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const columns = [
    { title: '提现单号', dataIndex: 'withdraw_no', key: 'withdraw_no' },
    { title: '店铺 ID', dataIndex: 'shop_id', key: 'shop_id' },
    { title: '申请时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '金额',
      dataIndex: 'amount_fen',
      key: 'amount_fen',
      render: (fen: number) => <b style={{ color: '#F31947' }}>¥{formatFen(fen)}</b>,
    },
    {
      title: '收款信息',
      dataIndex: 'account_info',
      key: 'account_info',
      render: (info: Record<string, string>) => `${info.holder ?? ''} ${info.account ?? ''}`.trim() || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: MallWithdrawStatus) => {
        const label = STATUS_LABELS[s]
        return <Tag color={label?.color}>{label?.text ?? s}</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: MallWithdraw) =>
        record.status === 'pending' ? (
          <div className="flex gap-1">
            <Button size="small" type="primary" onClick={() => { setApproved(true); setTarget(record) }}>
              确认打款
            </Button>
            <Button size="small" danger onClick={() => { setApproved(false); setTarget(record) }}>
              驳回
            </Button>
          </div>
        ) : (
          <span className="text-xs" style={{ color: '#999' }}>
            {record.reject_reason || record.handled_at || '-'}
          </span>
        ),
    },
  ]

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        提现审核
      </h3>
      <Tabs
        activeKey={status}
        items={TABS}
        onChange={(key) => setStatus(key as MallWithdrawStatus | '')}
        className="mb-2"
      />

      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{ current: page, pageSize: 10, total, onChange: setPage, showSizeChanger: false }}
      />

      <Modal
        title={approved ? '确认打款' : '驳回提现申请'}
        open={target != null}
        onCancel={() => setTarget(null)}
        onOk={submit}
        confirmLoading={submitting}
        okText="确认"
        cancelText="取消"
      >
        {approved ? (
          <p className="text-sm" style={{ color: '#666' }}>
            确认已向商家线下打款 ¥{target ? formatFen(target.amount_fen) : '0.00'}？
          </p>
        ) : (
          <Form form={form} layout="vertical" className="mt-4">
            <Form.Item name="reject_reason" label="驳回原因" rules={[{ required: true, message: '请填写驳回原因' }, { max: 200 }]}>
              <Input.TextArea rows={3} placeholder="如：收款信息有误" />
            </Form.Item>
          </Form>
        )}
      </Modal>
    </div>
  )
}
