import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Empty, Pagination, Spin } from 'antd'
import { getMallShopPublic, searchMallGoods } from '../../lib/mall'
import type { MallGoods, MallShopPublic } from '../../lib/types'
import { formatFen } from '../../lib/mallFormat'

type SortKey = 'default' | 'sales' | 'price_asc' | 'price_desc' | 'new'

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'default', label: '综合' },
  { key: 'sales', label: '销量' },
  { key: 'price_asc', label: '价格↑' },
  { key: 'price_desc', label: '价格↓' },
  { key: 'new', label: '最新' },
]

export default function MallShopPage() {
  const { shopId } = useParams<{ shopId: string }>()
  const id = shopId ? Number(shopId) : 0

  const [shop, setShop] = useState<MallShopPublic | null>(null)
  const [shopLoading, setShopLoading] = useState(false)
  const [sort, setSort] = useState<SortKey>('default')
  const [page, setPage] = useState(1)
  const [goods, setGoods] = useState<MallGoods[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!id) return
    setShopLoading(true)
    getMallShopPublic(id)
      .then(setShop)
      .catch(() => setShop(null))
      .finally(() => setShopLoading(false))
  }, [id])

  useEffect(() => {
    setPage(1)
  }, [sort])

  const load = useCallback(async () => {
    if (!id) return
    setLoading(true)
    try {
      const result = await searchMallGoods({
        shop_id: id,
        sort,
        page,
        page_size: 20,
      })
      setGoods(result.items)
      setTotal(result.total)
    } finally {
      setLoading(false)
    }
  }, [id, sort, page])

  useEffect(() => {
    load()
  }, [load])

  return (
    <div>
      <section className="rounded bg-white" style={{ padding: '20px 24px' }}>
        <Spin spinning={shopLoading}>
          {shop ? (
            <div className="flex items-center gap-4">
              {shop.avatar && (
                <img
                  src={shop.avatar}
                  alt={shop.name}
                  className="rounded-full object-cover"
                  style={{ width: 64, height: 64, border: '1px solid #f0f0f0' }}
                />
              )}
              <div>
                <div className="text-lg font-bold" style={{ color: '#333' }}>
                  {shop.name}
                </div>
                {shop.description && (
                  <div className="text-sm mt-1" style={{ color: '#888', maxWidth: 720 }}>
                    {shop.description}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="text-sm" style={{ color: '#999' }}>
              店铺信息加载中或不存在
            </div>
          )}
        </Spin>
      </section>

      <section className="rounded bg-white mt-4" style={{ padding: '12px 16px', minHeight: 360 }}>
        <div className="flex items-center gap-2 mb-3">
          {SORTS.map((s) => (
            <button
              key={s.key}
              type="button"
              onClick={() => setSort(s.key)}
              className="px-3 py-1 rounded text-sm cursor-pointer border-0"
              style={{
                background: sort === s.key ? '#F31947' : '#f2f2f2',
                color: sort === s.key ? '#fff' : '#555',
              }}
            >
              {s.label}
            </button>
          ))}
        </div>

        <Spin spinning={loading}>
          {goods.length === 0 ? (
            <Empty description="该店铺暂无在售商品" style={{ marginTop: 80 }} />
          ) : (
            <div className="grid grid-cols-4 gap-4">
              {goods.map((g) => (
                <Link
                  key={g.id}
                  to={`/mall/goods/${g.id}`}
                  className="block rounded overflow-hidden hover:shadow-md transition-shadow"
                  style={{ border: '1px solid #f0f0f0' }}
                >
                  <div className="aspect-square bg-gray-50 flex items-center justify-center">
                    <img src={g.main_image} alt={g.name} className="w-full h-full object-cover" />
                  </div>
                  <div className="p-2">
                    <div className="text-sm h-10 overflow-hidden" style={{ color: '#333' }}>
                      {g.name}
                    </div>
                    <div className="mt-1 flex items-baseline gap-2">
                      <span className="font-bold" style={{ color: '#F31947' }}>
                        ¥{formatFen(g.price_fen)}
                      </span>
                      {g.original_price_fen != null && (
                        <span className="text-xs line-through" style={{ color: '#999' }}>
                          ¥{formatFen(g.original_price_fen)}
                        </span>
                      )}
                    </div>
                    <div className="text-xs mt-1" style={{ color: '#999' }}>
                      已售 {g.sales} 件
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </Spin>

        {total > 20 && (
          <div className="flex justify-center mt-4 pb-2">
            <Pagination current={page} pageSize={20} total={total} onChange={setPage} showSizeChanger={false} />
          </div>
        )}
      </section>
    </div>
  )
}
