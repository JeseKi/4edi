import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { App, Button, Empty, Input, Modal, QRCode, Radio, Spin, Steps, Timeline } from 'antd'
import { WechatFilled } from '@ant-design/icons'
import {
  cancelMallOrder,
  confirmMallOrder,
  createMallPayment,
  createMallRefund,
  getMallPayment,
  getMallOrder,
  getMallOrderTraces,
  mockPayMallOrder,
  refreshMallPayment,
} from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen, MALL_ORDER_STATUS_LABELS } from '../../lib/mallFormat'
import type { MallOrder, MallRefundType } from '../../lib/types'

const STATUS_COLORS: Record<string, string> = {
  pending_payment: '#FA8C16',
  paid: '#1677FF',
  shipped: '#722ED1',
  completed: '#52C41A',
  cancelled: '#999',
  refunding: '#FA8C16',
  refunded: '#999',
}

export default function OrderDetailPage() {
  const { orderNo } = useParams<{ orderNo: string }>()
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [order, setOrder] = useState<MallOrder | null>(null)
  const [loading, setLoading] = useState(true)
  const [acting, setActing] = useState(false)
  const [payModalOpen, setPayModalOpen] = useState(false)
  const [paying, setPaying] = useState(false)
  const [payInfo, setPayInfo] = useState<{
    out_trade_no: string
    code_url: string | null
    mode: string
    expires_at: string
  } | null>(null)
  const [tracesOpen, setTracesOpen] = useState(false)
  const [traces, setTraces] = useState<string[]>([])
  const [refundModalOpen, setRefundModalOpen] = useState(false)
  const [refundType, setRefundType] = useState<MallRefundType>('refund_only')
  const [refundReason, setRefundReason] = useState('')
  const [refundDescription, setRefundDescription] = useState('')
  const [refunding, setRefunding] = useState(false)

  const load = useCallback(async () => {
    if (!orderNo) return
    setLoading(true)
    try {
      setOrder(await getMallOrder(orderNo))
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '订单加载失败'))
    } finally {
      setLoading(false)
    }
  }, [orderNo, message])

  useEffect(() => {
    load()
  }, [load])

  const handleCancel = async () => {
    if (!order) return
    setActing(true)
    try {
      setOrder(await cancelMallOrder(order.order_no))
      message.success('订单已取消')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '取消失败'))
    } finally {
      setActing(false)
    }
  }

  const handleConfirm = async () => {
    if (!order) return
    setActing(true)
    try {
      setOrder(await confirmMallOrder(order.order_no))
      message.success('已确认收货，货款已解冻给商家')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setActing(false)
    }
  }

  const handlePay = async () => {
    if (!order) return
    setPaying(true)
    try {
      const prepay = await createMallPayment(order.order_no, 'native')
      setPayInfo({
        out_trade_no: prepay.out_trade_no,
        code_url: prepay.code_url,
        mode: prepay.mode,
        expires_at: prepay.expires_at,
      })
      setPayModalOpen(true)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '发起支付失败'))
    } finally {
      setPaying(false)
    }
  }

  const handleMockPay = async () => {
    if (!payInfo) return
    setPaying(true)
    try {
      await mockPayMallOrder(payInfo.out_trade_no)
      message.success('支付成功')
      setPayModalOpen(false)
      await load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '支付失败'))
    } finally {
      setPaying(false)
    }
  }

  const handleRefreshPayment = async () => {
    if (!order) return
    setPaying(true)
    try {
      const payment = await refreshMallPayment(order.order_no)
      if (payment.status === 'success') {
        message.success('支付成功')
        setPayModalOpen(false)
        await load()
      } else {
        message.info('暂未查询到支付成功，请稍后重试')
      }
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '支付状态刷新失败'))
    } finally {
      setPaying(false)
    }
  }

  useEffect(() => {
    if (!payModalOpen || !order || payInfo?.mode === 'mock') return
    let cancelled = false
    const poll = async () => {
      try {
        const payment = await getMallPayment(order.order_no)
        if (!cancelled && payment.status === 'success') {
          message.success('支付成功')
          setPayModalOpen(false)
          await load()
        }
      } catch {
        // 支付弹窗的后台轮询不干扰用户主动操作。
      }
    }
    void poll()
    const timer = window.setInterval(() => void poll(), 3000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [load, message, order, payInfo?.mode, payModalOpen])

  const showTraces = async () => {
    if (!order) return
    try {
      const result = await getMallOrderTraces(order.order_no)
      setTraces(result.traces)
      setTracesOpen(true)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '物流加载失败'))
    }
  }

  const openRefundModal = () => {
    if (!order) return
    setRefundType(order.status === 'paid' ? 'refund_only' : 'return_refund')
    setRefundReason('')
    setRefundDescription('')
    setRefundModalOpen(true)
  }

  const handleApplyRefund = async () => {
    if (!order) return
    if (!refundReason.trim()) {
      message.warning('请填写退款原因')
      return
    }
    setRefunding(true)
    try {
      await createMallRefund({
        order_no: order.order_no,
        type: refundType,
        reason: refundReason.trim(),
        description: refundDescription.trim() || undefined,
      })
      message.success('退款申请已提交，等待卖家处理')
      setRefundModalOpen(false)
      navigate('/mall/refunds')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '申请失败'))
    } finally {
      setRefunding(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    )
  }

  if (!order) {
    return <Empty description="订单不存在" style={{ marginTop: 80 }} />
  }

  const stepIndex = ['pending_payment', 'paid', 'shipped', 'completed'].indexOf(order.status)

  return (
    <div className="space-y-4">
      <section className="rounded bg-white" style={{ padding: '20px 24px' }}>
        <div className="flex items-center justify-between">
          <div>
            <span className="text-xl font-bold" style={{ color: STATUS_COLORS[order.status] }}>
              {MALL_ORDER_STATUS_LABELS[order.status] ?? order.status}
            </span>
            {order.cancel_reason && (
              <span className="text-xs ml-3" style={{ color: '#999' }}>
                取消原因：{order.cancel_reason}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            {order.status === 'pending_payment' && (
              <>
                <Button onClick={handleCancel} loading={acting}>
                  取消订单
                </Button>
                <Button type="primary" loading={paying} onClick={handlePay} style={{ background: '#F31947' }}>
                  立即支付
                </Button>
              </>
            )}
            {order.status === 'shipped' && (
              <>
                <Button onClick={showTraces}>查看物流</Button>
                <Button onClick={openRefundModal}>申请退款</Button>
                <Button type="primary" onClick={handleConfirm} loading={acting} style={{ background: '#F31947' }}>
                  确认收货
                </Button>
              </>
            )}
            {order.status === 'paid' && (
              <>
                <Button onClick={openRefundModal}>申请退款</Button>
                <Button
                  onClick={() =>
                    navigate(`/mall/chat?shop_id=${order.shop_id}&order_no=${order.order_no}`)
                  }
                >
                  联系卖家催发货
                </Button>
              </>
            )}
            {order.status === 'completed' && (
              <>
                <Button onClick={showTraces}>查看物流</Button>
                <Button onClick={openRefundModal}>申请退款</Button>
                <Button
                  type="primary"
                  style={{ background: '#F31947' }}
                  onClick={() => navigate(`/mall/evaluations?order_no=${order.order_no}`)}
                >
                  去评价
                </Button>
              </>
            )}
            {order.status === 'refunding' && (
              <>
                <Button onClick={showTraces}>查看物流</Button>
                <Link to="/mall/refunds">
                  <Button type="primary" style={{ background: '#F31947' }}>
                    查看退款进度
                  </Button>
                </Link>
              </>
            )}
            {order.status === 'cancelled' && (
              <Button onClick={showTraces}>查看物流</Button>
            )}
          </div>
        </div>
        {stepIndex >= 0 && (
          <Steps
            size="small"
            className="mt-5"
            current={stepIndex}
            items={[
              { title: '提交订单' },
              { title: '付款' },
              { title: '发货' },
              { title: '完成' },
            ]}
          />
        )}
      </section>

      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h4 className="text-sm font-bold mb-2" style={{ color: '#333' }}>
          收货信息
        </h4>
        <div className="text-sm" style={{ color: '#666' }}>
          {order.receiver_name} {order.receiver_phone} · {order.receiver_address}
        </div>
        {order.shipping_company && (
          <div className="text-xs mt-1" style={{ color: '#999' }}>
            {order.shipping_company} {order.tracking_no}
          </div>
        )}
      </section>

      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h4 className="text-sm font-bold mb-2" style={{ color: '#333' }}>
          商品信息
        </h4>
        {order.items.map((item) => (
          <div key={item.id} className="flex items-center gap-3 py-2" style={{ borderBottom: '1px solid #f5f5f5' }}>
            <img
              src={item.goods_image}
              alt={item.goods_name}
              className="rounded"
              style={{ width: 56, height: 56, objectFit: 'cover', background: '#f7f7f7' }}
            />
            <div className="flex-1">
              <div className="text-sm" style={{ color: '#333' }}>
                {item.goods_name}
              </div>
              <div className="text-xs mt-1" style={{ color: '#999' }}>
                {Object.entries(item.sku_specs)
                  .map(([k, v]) => `${k}:${v}`)
                  .join(' · ')}
              </div>
            </div>
            <span className="text-sm">
              ¥{formatFen(item.unit_price_fen)} × {item.quantity}
            </span>
            <span className="font-bold" style={{ color: '#F31947', width: 90, textAlign: 'right' }}>
              ¥{formatFen(item.subtotal_fen)}
            </span>
          </div>
        ))}
        <div className="text-right mt-3 text-sm" style={{ color: '#666' }}>
          商品金额：¥{formatFen(order.goods_amount_fen)} · 运费：¥{formatFen(order.freight_fen)}
          <div className="mt-1">
            实付：
            <span className="text-lg font-bold" style={{ color: '#F31947' }}>
              ¥{formatFen(order.pay_amount_fen)}
            </span>
          </div>
        </div>
        {order.remark && (
          <div className="text-xs mt-2" style={{ color: '#999' }}>
            备注：{order.remark}
          </div>
        )}
      </section>

      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h4 className="text-sm font-bold mb-2" style={{ color: '#333' }}>
          订单动态
        </h4>
        <Timeline
          items={[...order.logs]
            .sort((a, b) => a.id - b.id)
            .map((log) => ({
              children: (
                <span className="text-sm" style={{ color: '#555' }}>
                  {log.message}
                  <span className="text-xs ml-2" style={{ color: '#999' }}>
                    {log.created_at}
                  </span>
                </span>
              ),
            }))}
        />
        <div className="mt-2">
          <Link to={`/mall/chat?shop_id=${order.shop_id}&order_no=${order.order_no}`}>
            <Button size="small">联系客服</Button>
          </Link>
        </div>
      </section>

      <Modal
        title="微信支付"
        open={payModalOpen}
        onCancel={() => setPayModalOpen(false)}
        footer={null}
        width={380}
      >
        <div className="text-center py-2">
          <div className="text-sm mb-1" style={{ color: '#999' }}>
            应付金额
          </div>
          <div className="text-2xl font-bold mb-4" style={{ color: '#F31947' }}>
            ¥{order ? formatFen(order.pay_amount_fen) : ''}
          </div>
          {payInfo?.mode === 'mock' ? (
            <>
              <div
                className="mx-auto mb-4 flex items-center justify-center text-white"
                style={{ width: 180, height: 180, borderRadius: 12, background: '#262626' }}
              >
                <div className="text-center">
                  <div className="text-lg mb-1">微信</div>
                  <div className="text-xs opacity-80">本地开发演示</div>
                </div>
              </div>
              <div className="text-xs mb-4" style={{ color: '#999' }}>
                当前为本地开发模式，点击下方按钮完成支付演示
              </div>
              <Button type="primary" block loading={paying} onClick={handleMockPay} style={{ background: '#F31947' }}>
                完成支付演示
              </Button>
            </>
          ) : (
            <>
              <div className="mb-4 flex items-center justify-center gap-2 text-sm" style={{ color: '#07C160' }}>
                <WechatFilled style={{ fontSize: 20 }} />
                <span>微信支付</span>
              </div>
              <div className="text-xs mb-4" style={{ color: '#999' }}>
                请使用微信扫描二维码完成支付
              </div>
              {payInfo?.code_url ? (
                <div className="mb-4 flex w-full justify-center">
                  <QRCode value={payInfo.code_url} size={200} />
                </div>
              ) : (
                <Spin className="mb-4" />
              )}
              <div className="text-xs mb-4" style={{ color: '#999' }}>
                支付完成后会自动更新；若回调延迟，可手动刷新。
              </div>
              <Button block loading={paying} onClick={handleRefreshPayment}>
                已支付，刷新状态
              </Button>
            </>
          )}
        </div>
      </Modal>

      <Modal title="物流轨迹" open={tracesOpen} onCancel={() => setTracesOpen(false)} footer={null} width={420}>
        <Timeline
          items={traces.map((trace) => ({
            children: <span className="text-sm">{trace}</span>,
          }))}
        />
      </Modal>

      <Modal
        title="申请退款"
        open={refundModalOpen}
        onCancel={() => setRefundModalOpen(false)}
        onOk={handleApplyRefund}
        confirmLoading={refunding}
        okText="提交申请"
        cancelText="取消"
        width={440}
      >
        <div className="mt-2 space-y-3">
          <div className="text-sm" style={{ color: '#666' }}>
            退款金额：<b style={{ color: '#F31947' }}>¥{order ? formatFen(order.pay_amount_fen) : ''}</b>
            <span className="text-xs ml-2" style={{ color: '#999' }}>
              提交后订单将进入退款流程，需卖家处理
            </span>
          </div>
          <div>
            <div className="text-sm mb-1" style={{ color: '#555' }}>
              退款类型
            </div>
            <Radio.Group
              value={refundType}
              onChange={(e) => setRefundType(e.target.value)}
              options={[
                { label: '仅退款（未发货）', value: 'refund_only', disabled: order?.status !== 'paid' },
                { label: '退货退款（已发货）', value: 'return_refund', disabled: order?.status === 'paid' },
              ]}
            />
          </div>
          <Input
            placeholder="退款原因（必填）"
            maxLength={200}
            value={refundReason}
            onChange={(e) => setRefundReason(e.target.value)}
          />
          <Input.TextArea
            placeholder="补充说明（选填）"
            maxLength={1000}
            rows={3}
            value={refundDescription}
            onChange={(e) => setRefundDescription(e.target.value)}
          />
        </div>
      </Modal>
    </div>
  )
}
