import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { App, Button, Form, Input, Modal, Pagination, Select, Spin, Tag, Timeline } from 'antd'
import {
  cancelMallRefund,
  listMyMallRefunds,
  submitMallRefundReturnTracking,
} from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import {
  formatFen,
  MALL_REFUND_STATUS_LABELS,
  MALL_REFUND_TYPE_LABELS,
} from '../../lib/mallFormat'
import type { MallRefund } from '../../lib/types'

const STATUS_TAG_COLOR: Record<string, string> = {
  pending: 'orange',
  returning: 'geekblue',
  refunding: 'purple',
  success: 'green',
  rejected: 'red',
  cancelled: 'default',
}

export default function RefundListPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [page, setPage] = useState(1)
  const [refunds, setRefunds] = useState<MallRefund[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [trackingTarget, setTrackingTarget] = useState<MallRefund | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [actingNo, setActingNo] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listMyMallRefunds({ page, page_size: 10 })
      setRefunds(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '退款列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, message])

  useEffect(() => {
    load()
  }, [load])

  const handleCancel = async (refund: MallRefund) => {
    setActingNo(refund.refund_no)
    try {
      await cancelMallRefund(refund.refund_no)
      message.success('退款申请已取消')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '取消失败'))
    } finally {
      setActingNo(null)
    }
  }

  const submitTracking = async () => {
    if (!trackingTarget) return
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await submitMallRefundReturnTracking(trackingTarget.refund_no, values)
      message.success('退货物流已提交，等待卖家确认')
      setTrackingTarget(null)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '提交失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        退款 / 售后
      </h3>

      <Spin spinning={loading}>
        {refunds.map((refund) => {
          const steps: { title: string; description?: string }[] = [
            { title: '提交申请' },
            { title: '卖家处理', description: refund.refuse_reason ?? undefined },
            ...(refund.type === 'return_refund'
              ? [
                  { title: '退货寄回' },
                  { title: '卖家确认收货' },
                ]
              : []),
            { title: '退款完成' },
          ]
          const stepIndex =
            refund.status === 'pending'
              ? 0
              : refund.status === 'returning'
                ? 1
                : refund.status === 'refunding'
                  ? 1
                  : refund.status === 'success'
                    ? steps.length - 1
                    : 0
          return (
            <div key={refund.refund_no} className="mb-4 rounded" style={{ border: '1px solid #f0f0f0' }}>
              <div
                className="flex items-center justify-between px-4 py-2 text-xs"
                style={{ background: '#fafafa', color: '#666' }}
              >
                <span>
                  {refund.created_at} · 退款单 {refund.refund_no} ·{' '}
                  <Link to={`/mall/orders/${refund.order_no}`} className="hover:opacity-80">
                    订单 {refund.order_no}
                  </Link>
                </span>
                <Tag color={STATUS_TAG_COLOR[refund.status]}>
                  {MALL_REFUND_STATUS_LABELS[refund.status] ?? refund.status}
                </Tag>
              </div>
              <div className="px-4 py-3 text-sm" style={{ color: '#555' }}>
                {refund.shop_name} · {MALL_REFUND_TYPE_LABELS[refund.type] ?? refund.type} ·{' '}
                {refund.reason}
                <span className="ml-2 font-bold" style={{ color: '#F31947' }}>
                  退款 ¥{formatFen(refund.amount_fen)}
                </span>
              </div>
              <div className="flex items-center justify-between px-4 pb-3">
                <Button size="small" type="link" onClick={() => setExpanded(expanded === refund.refund_no ? null : refund.refund_no)}>
                  {expanded === refund.refund_no ? '收起详情' : '查看进度'}
                </Button>
                <div className="flex gap-2">
                  {refund.status === 'pending' && (
                    <Button size="small" danger loading={actingNo === refund.refund_no} onClick={() => handleCancel(refund)}>
                      取消申请
                    </Button>
                  )}
                  {refund.status === 'returning' && (
                    <Button size="small" type="primary" style={{ background: '#F31947' }} onClick={() => setTrackingTarget(refund)}>
                      填写退货物流
                    </Button>
                  )}
                </div>
              </div>
              {expanded === refund.refund_no && (
                <div className="px-4 pb-4" style={{ borderTop: '1px solid #f5f5f5' }}>
                  <Timeline
                    className="mt-3"
                    items={steps.map((step, index) => ({
                      children: (
                        <span className="text-sm" style={{ color: '#555' }}>
                          {step.title}
                          {step.description && (
                            <span className="text-xs ml-2" style={{ color: '#999' }}>
                              {step.description}
                            </span>
                          )}
                        </span>
                      ),
                      color: index < stepIndex ? 'green' : index === stepIndex && refund.status !== 'rejected' && refund.status !== 'cancelled' ? 'blue' : 'gray',
                    }))}
                  />
                  {refund.description && (
                    <div className="text-xs mt-2" style={{ color: '#999' }}>
                      说明：{refund.description}
                    </div>
                  )}
                  {refund.return_tracking_no && (
                    <div className="text-xs mt-1" style={{ color: '#999' }}>
                      退货物流：{refund.return_tracking_company} {refund.return_tracking_no}
                    </div>
                  )}
                  {refund.status === 'success' && refund.success_at && (
                    <div className="text-xs mt-1" style={{ color: '#52C41A' }}>
                      退款到账时间：{refund.success_at}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
        {!loading && refunds.length === 0 && (
          <div className="text-center py-16 text-sm" style={{ color: '#999' }}>
            暂无退款记录
          </div>
        )}
      </Spin>

      {total > 10 && (
        <div className="flex justify-center mt-4">
          <Pagination current={page} pageSize={10} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}

      <Modal
        title={`填写退货物流（${trackingTarget?.refund_no ?? ''}）`}
        open={trackingTarget != null}
        onCancel={() => setTrackingTarget(null)}
        onOk={submitTracking}
        confirmLoading={submitting}
        okText="提交"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="return_tracking_company" label="物流公司" rules={[{ required: true, message: '请选择物流公司' }]}>
            <Select
              placeholder="选择物流公司"
              options={['顺丰速运', '中通快递', '圆通速递', '韵达快递', '京东物流'].map((name) => ({
                label: name,
                value: name,
              }))}
            />
          </Form.Item>
          <Form.Item name="return_tracking_no" label="运单号" rules={[{ required: true, message: '请输入运单号' }, { max: 50 }]}>
            <Input placeholder="快递运单号" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
