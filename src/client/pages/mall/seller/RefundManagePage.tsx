import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { App, Button, Form, Modal, Pagination, Select, Space, Spin, Tabs, Tag } from 'antd'
import {
  agreeSellerRefund,
  confirmSellerRefundReturn,
  listSellerRefunds,
  rejectSellerRefund,
} from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import {
  formatFen,
  MALL_REFUND_STATUS_LABELS,
  MALL_REFUND_TYPE_LABELS,
} from '../../../lib/mallFormat'
import type { MallRefund, MallRefundStatus } from '../../../lib/types'

const TABS = [
  { key: '', label: '全部' },
  { key: 'pending', label: '待处理' },
  { key: 'returning', label: '退货中' },
  { key: 'refunding', label: '退款中' },
  { key: 'success', label: '退款成功' },
  { key: 'rejected', label: '已拒绝' },
]

const STATUS_TAG_COLOR: Record<string, string> = {
  pending: 'orange',
  returning: 'geekblue',
  refunding: 'purple',
  success: 'green',
  rejected: 'red',
  cancelled: 'default',
}

export default function RefundManagePage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [status, setStatus] = useState<MallRefundStatus | ''>('')
  const [page, setPage] = useState(1)
  const [refunds, setRefunds] = useState<MallRefund[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [actingNo, setActingNo] = useState<string | null>(null)
  const [rejectTarget, setRejectTarget] = useState<MallRefund | null>(null)
  const [rejecting, setRejecting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listSellerRefunds({ status: status || undefined, page, page_size: 10 })
      setRefunds(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '退款列表加载失败'))
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

  const handleAgree = async (refund: MallRefund) => {
    setActingNo(refund.refund_no)
    try {
      await agreeSellerRefund(refund.refund_no)
      message.success(refund.type === 'return_refund' ? '已同意退货，等待买家寄回' : '已同意退款')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setActingNo(null)
    }
  }

  const handleConfirmReturn = async (refund: MallRefund) => {
    setActingNo(refund.refund_no)
    try {
      await confirmSellerRefundReturn(refund.refund_no)
      message.success('已确认收到退货，退款处理中')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setActingNo(null)
    }
  }

  const submitReject = async () => {
    if (!rejectTarget) return
    const values = await form.validateFields()
    setRejecting(true)
    try {
      await rejectSellerRefund(rejectTarget.refund_no, { reason: values.reason })
      message.success('已拒绝退款申请')
      setRejectTarget(null)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setRejecting(false)
    }
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        退款管理
      </h3>
      <Tabs
        activeKey={status}
        items={TABS.map((t) => ({ key: t.key, label: t.label }))}
        onChange={(key) => setStatus(key as MallRefundStatus | '')}
      />

      <Spin spinning={loading}>
        {refunds.map((refund) => (
          <div key={refund.refund_no} className="mb-4 rounded" style={{ border: '1px solid #f0f0f0' }}>
            <div
              className="flex items-center justify-between px-4 py-2 text-xs"
              style={{ background: '#fafafa', color: '#666' }}
            >
              <span>
                {refund.created_at} · 退款单 {refund.refund_no}
              </span>
              <Tag color={STATUS_TAG_COLOR[refund.status]}>
                {MALL_REFUND_STATUS_LABELS[refund.status] ?? refund.status}
              </Tag>
            </div>
            <div className="px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="text-sm" style={{ color: '#555' }}>
                  {MALL_REFUND_TYPE_LABELS[refund.type] ?? refund.type} · {refund.reason}
                  {refund.refuse_reason && (
                    <span className="text-xs ml-2" style={{ color: '#F31947' }}>
                      拒绝原因：{refund.refuse_reason}
                    </span>
                  )}
                </div>
                <span className="text-sm shrink-0 ml-3">
                  退款 <b style={{ color: '#F31947' }}>¥{formatFen(refund.amount_fen)}</b>
                </span>
              </div>
              <div className="text-xs mt-2" style={{ color: '#999' }}>
                <Link to={`/mall/orders/${refund.order_no}`} className="hover:opacity-80">
                  订单 {refund.order_no}
                </Link>
                {refund.return_tracking_no && (
                  <span className="ml-3">
                    退货物流：{refund.return_tracking_company} {refund.return_tracking_no}
                  </span>
                )}
              </div>
              <div className="flex justify-end mt-3">
                <Space>
                  {refund.status === 'pending' && (
                    <>
                      <Button size="small" danger loading={actingNo === refund.refund_no} onClick={() => setRejectTarget(refund)}>
                        拒绝
                      </Button>
                      <Button size="small" type="primary" style={{ background: '#F31947' }} loading={actingNo === refund.refund_no} onClick={() => handleAgree(refund)}>
                        {refund.type === 'return_refund' ? '同意退货' : '同意退款'}
                      </Button>
                    </>
                  )}
                  {refund.status === 'returning' && (
                    <Button size="small" type="primary" style={{ background: '#F31947' }} loading={actingNo === refund.refund_no} onClick={() => handleConfirmReturn(refund)}>
                      确认收到退货
                    </Button>
                  )}
                </Space>
              </div>
            </div>
          </div>
        ))}
        {!loading && refunds.length === 0 && (
          <div className="text-center py-16 text-sm" style={{ color: '#999' }}>
            暂无退款申请
          </div>
        )}
      </Spin>

      {total > 10 && (
        <div className="flex justify-center mt-4">
          <Pagination current={page} pageSize={10} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}

      <Modal
        title={`拒绝退款（${rejectTarget?.refund_no ?? ''}）`}
        open={rejectTarget != null}
        onCancel={() => setRejectTarget(null)}
        onOk={submitReject}
        confirmLoading={rejecting}
        okText="确认拒绝"
        cancelText="取消"
        okButtonProps={{ danger: true }}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="reason" label="拒绝原因" rules={[{ required: true, message: '请填写拒绝原因' }, { max: 200 }]}>
            <Select
              placeholder="选择或输入拒绝原因"
              showSearch
              options={['商品无质量问题', '商品已签收且完好', '不符合退款条件'].map((name) => ({
                label: name,
                value: name,
              }))}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
