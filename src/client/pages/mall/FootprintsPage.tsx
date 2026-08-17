import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { App, Empty, Pagination, Spin } from 'antd'
import { ClockCircleOutlined } from '@ant-design/icons'
import { listMyFootprints } from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen } from '../../lib/mallFormat'
import type { MallFootprint } from '../../lib/types'

export default function FootprintsPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [items, setItems] = useState<MallFootprint[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listMyFootprints({ page, page_size: 20 })
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '浏览足迹加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, message])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        我的浏览足迹
      </h3>

      <Spin spinning={loading}>
        {items.length === 0 ? (
          <Empty description="暂无浏览记录" style={{ marginTop: 48 }} />
        ) : (
          <div className="space-y-3">
            {items.map((footprint) => (
              <div
                key={`${footprint.goods_id}-${footprint.viewed_at}`}
                className="flex items-center gap-4 rounded px-3 py-3 cursor-pointer"
                style={{ border: '1px solid #f0f0f0', background: '#fff' }}
                onClick={() => navigate(`/mall/goods/${footprint.goods_id}`)}
              >
                {footprint.goods_image ? (
                  <img
                    src={footprint.goods_image}
                    alt={footprint.goods_name ?? '商品'}
                    className="rounded shrink-0"
                    style={{ width: 80, height: 80, objectFit: 'cover', background: '#fafafa' }}
                  />
                ) : (
                  <div className="rounded shrink-0 flex items-center justify-center" style={{ width: 80, height: 80, background: '#fafafa' }}>
                    <ClockCircleOutlined style={{ fontSize: 24, color: '#ddd' }} />
                  </div>
                )}
                <div className="flex-1 min-w-0">
                  <div className="text-sm truncate" style={{ color: '#333' }}>
                    {footprint.goods_name ?? '商品已下架'}
                  </div>
                  <div className="text-xs mt-1" style={{ color: '#999' }}>
                    {footprint.shop_name ?? '店铺'}{footprint.price_fen != null ? ` · ¥${formatFen(footprint.price_fen)}` : ''}
                  </div>
                  <div className="text-xs mt-1" style={{ color: '#bbb' }}>
                    浏览于 {footprint.viewed_at?.slice(0, 19).replace('T', ' ')}
                  </div>
                </div>
                <span className="text-sm shrink-0" style={{ color: '#F31947' }}>
                  {footprint.price_fen != null ? `¥${formatFen(footprint.price_fen)}` : '—'}
                </span>
              </div>
            ))}
          </div>
        )}
      </Spin>

      {total > 20 && (
        <div className="flex justify-center mt-4">
          <Pagination current={page} pageSize={20} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}
    </div>
  )
}
