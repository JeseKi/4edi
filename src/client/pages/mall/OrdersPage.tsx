import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { App, Button, Empty, Pagination, Spin, Tabs } from 'antd'
import { listMallOrders } from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen, MALL_ORDER_STATUS_LABELS } from '../../lib/mallFormat'
import type { MallOrder, MallOrderStatus } from '../../lib/types'

const TABS: { key: string; label: string }[] = [
  { key: '', label: '全部' },
  { key: 'pending_payment', label: '待付款' },
  { key: 'paid', label: '待发货' },
  { key: 'shipped', label: '待收货' },
  { key: 'completed', label: '已完成' },
  { key: 'refunding', label: '退款中' },
  { key: 'refunded', label: '已退款' },
  { key: 'cancelled', label: '已取消' },
]

export default function OrdersPage() {
  const { message } = App.useApp()
  const [searchParams, setSearchParams] = useSearchParams()
  const status = (searchParams.get('status') ?? '') as MallOrderStatus | ''
  const [page, setPage] = useState(1)
  const [orders, setOrders] = useState<MallOrder[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listMallOrders({
        status: status || undefined,
        page,
        page_size: 10,
      })
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

  const changeTab = (key: string) => {
    const next = new URLSearchParams(searchParams)
    if (key) next.set('status', key)
    else next.delete('status')
    setSearchParams(next)
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h2 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        我的订单
      </h2>
      <Tabs activeKey={status} items={TABS.map((t) => ({ key: t.key, label: t.label }))} onChange={changeTab} />

      <Spin spinning={loading}>
        {orders.length === 0 && !loading ? (
          <Empty description="暂无订单" style={{ marginTop: 60, marginBottom: 60 }} />
        ) : (
          orders.map((order) => (
            <div
              key={order.order_no}
              className="mb-4 rounded"
              style={{ border: '1px solid #f0f0f0' }}
            >
              <div
                className="flex items-center justify-between px-4 py-2 text-xs"
                style={{ background: '#fafafa', color: '#666' }}
              >
                <span>
                  {order.created_at} · 订单号 {order.order_no}
                </span>
                <span className="font-bold" style={{ color: '#F31947' }}>
                  {MALL_ORDER_STATUS_LABELS[order.status] ?? order.status}
                </span>
              </div>
              {order.items.map((item) => (
                <Link
                  key={item.id}
                  to={`/mall/orders/${order.order_no}`}
                  className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50"
                >
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
                </Link>
              ))}
              <div className="flex items-center justify-end gap-3 px-4 py-3">
                <span className="text-sm">
                  实付：<span className="font-bold" style={{ color: '#F31947' }}>¥{formatFen(order.pay_amount_fen)}</span>
                </span>
                <Link to={`/mall/orders/${order.order_no}`}>
                  <Button size="small">查看详情</Button>
                </Link>
              </div>
            </div>
          ))
        )}
      </Spin>

      {total > 10 && (
        <div className="flex justify-center mt-4 pb-2">
          <Pagination current={page} pageSize={10} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}
    </div>
  )
}
