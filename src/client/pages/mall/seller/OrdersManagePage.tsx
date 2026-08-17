import { useCallback, useEffect, useState } from 'react'
import { App, Button, Form, Input, Modal, Pagination, Select, Space, Spin, Tabs, Tag } from 'antd'
import { listSellerOrders, shipSellerOrder } from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import { formatFen, MALL_ORDER_STATUS_LABELS } from '../../../lib/mallFormat'
import type { MallOrder, MallOrderStatus } from '../../../lib/types'

const TABS = [
  { key: '', label: '全部' },
  { key: 'pending_payment', label: '待付款' },
  { key: 'paid', label: '待发货' },
  { key: 'shipped', label: '待收货' },
  { key: 'completed', label: '已完成' },
  { key: 'refunding', label: '退款中' },
  { key: 'refunded', label: '已退款' },
  { key: 'cancelled', label: '已取消' },
]

const STATUS_TAG_COLOR: Record<string, string> = {
  pending_payment: 'orange',
  paid: 'blue',
  shipped: 'purple',
  completed: 'green',
  cancelled: 'default',
  refunding: 'orange',
  refunded: 'default',
}

export default function SellerOrdersPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [status, setStatus] = useState<MallOrderStatus | ''>('')
  const [page, setPage] = useState(1)
  const [orders, setOrders] = useState<MallOrder[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [shipTarget, setShipTarget] = useState<MallOrder | null>(null)
  const [shipping, setShipping] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listSellerOrders({ status: status || undefined, page, page_size: 10 })
      setOrders(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '订单加载失败'))
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

  const submitShip = async () => {
    if (!shipTarget) return
    const values = await form.validateFields()
    setShipping(true)
    try {
      await shipSellerOrder(shipTarget.order_no, values)
      message.success('发货成功')
      setShipTarget(null)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '发货失败'))
    } finally {
      setShipping(false)
    }
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        订单管理
      </h3>
      <Tabs
        activeKey={status}
        items={TABS.map((t) => ({ key: t.key, label: t.label }))}
        onChange={(key) => setStatus(key as MallOrderStatus | '')}
      />

      <Spin spinning={loading}>
        {orders.map((order) => (
          <div key={order.order_no} className="mb-4 rounded" style={{ border: '1px solid #f0f0f0' }}>
            <div
              className="flex items-center justify-between px-4 py-2 text-xs"
              style={{ background: '#fafafa', color: '#666' }}
            >
              <span>
                {order.created_at} · 订单号 {order.order_no}
              </span>
              <Tag color={STATUS_TAG_COLOR[order.status]}>
                {MALL_ORDER_STATUS_LABELS[order.status] ?? order.status}
              </Tag>
            </div>
            {order.items.map((item) => (
              <div key={item.id} className="flex items-center gap-3 px-4 py-3">
                <img
                  src={item.goods_image}
                  alt={item.goods_name}
                  className="rounded"
                  style={{ width: 48, height: 48, objectFit: 'cover', background: '#f7f7f7' }}
                />
                <div className="flex-1">
                  <div className="text-sm">{item.goods_name}</div>
                  <div className="text-xs mt-1" style={{ color: '#999' }}>
                    {Object.entries(item.sku_specs)
                      .map(([k, v]) => `${k}:${v}`)
                      .join(' · ')}{' '}
                    × {item.quantity}
                  </div>
                </div>
              </div>
            ))}
            <div className="flex items-center justify-between px-4 py-3" style={{ borderTop: '1px solid #f5f5f5' }}>
              <span className="text-xs" style={{ color: '#999' }}>
                收货人：{order.receiver_name} {order.receiver_phone} · {order.receiver_address}
              </span>
              <Space>
                <span className="text-sm">
                  实付 <b style={{ color: '#F31947' }}>¥{formatFen(order.pay_amount_fen)}</b>
                </span>
                {order.status === 'paid' && (
                  <Button type="primary" size="small" onClick={() => setShipTarget(order)} style={{ background: '#F31947' }}>
                    发货
                  </Button>
                )}
              </Space>
            </div>
          </div>
        ))}
        {!loading && orders.length === 0 && (
          <div className="text-center py-16 text-sm" style={{ color: '#999' }}>
            暂无订单
          </div>
        )}
      </Spin>

      {total > 10 && (
        <div className="flex justify-center mt-4">
          <Pagination current={page} pageSize={10} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}

      <Modal
        title={`发货（订单 ${shipTarget?.order_no ?? ''}）`}
        open={shipTarget != null}
        onCancel={() => setShipTarget(null)}
        onOk={submitShip}
        confirmLoading={shipping}
        okText="确认发货"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="shipping_company" label="物流公司" rules={[{ required: true, message: '请选择物流公司' }]}>
            <Select
              placeholder="选择物流公司"
              options={['顺丰速运', '中通快递', '圆通速递', '韵达快递', '京东物流'].map((name) => ({
                label: name,
                value: name,
              }))}
            />
          </Form.Item>
          <Form.Item name="tracking_no" label="运单号" rules={[{ required: true, message: '请输入运单号' }, { max: 50 }]}>
            <Input placeholder="快递运单号" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
