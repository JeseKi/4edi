import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { Empty, Pagination, Spin } from 'antd'
import { listMallCategories, searchMallGoods } from '../../lib/mall'
import type { MallCategory, MallGoods } from '../../lib/types'
import { formatFen } from '../../lib/mallFormat'

type SortKey = 'default' | 'sales' | 'price_asc' | 'price_desc' | 'new'

const SORTS: { key: SortKey; label: string }[] = [
  { key: 'default', label: '综合' },
  { key: 'sales', label: '销量' },
  { key: 'price_asc', label: '价格↑' },
  { key: 'price_desc', label: '价格↓' },
  { key: 'new', label: '最新' },
]

type CategoryNode = MallCategory & { children: CategoryNode[] }

function buildTree(categories: MallCategory[]): CategoryNode[] {
  const byId = new Map<number, CategoryNode>(
    categories.map((c) => [c.id, { ...c, children: [] }]),
  )
  const roots: CategoryNode[] = []
  for (const category of byId.values()) {
    if (category.parent_id && byId.has(category.parent_id)) {
      byId.get(category.parent_id)!.children.push(category)
    } else {
      roots.push(category)
    }
  }
  return roots
}

export default function MallHomePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const keyword = searchParams.get('keyword') ?? ''
  const categoryId = searchParams.get('category_id') ? Number(searchParams.get('category_id')) : undefined
  const shopId = searchParams.get('shop_id') ? Number(searchParams.get('shop_id')) : undefined
  const [sort, setSort] = useState<SortKey>('default')
  const [page, setPage] = useState(1)
  const [goods, setGoods] = useState<MallGoods[]>([])
  const [total, setTotal] = useState(0)
  const [categories, setCategories] = useState<MallCategory[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    listMallCategories()
      .then(setCategories)
      .catch(() => {
        // 分类加载失败不阻塞商品浏览
      })
  }, [])

  useEffect(() => {
    setPage(1)
  }, [keyword, categoryId, shopId, sort])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await searchMallGoods({
        keyword: keyword || undefined,
        category_id: categoryId,
        shop_id: shopId,
        sort,
        page,
        page_size: 20,
      })
      setGoods(result.items)
      setTotal(result.total)
    } finally {
      setLoading(false)
    }
  }, [keyword, categoryId, shopId, sort, page])

  useEffect(() => {
    load()
  }, [load])

  const tree = useMemo(() => buildTree(categories), [categories])

  const pickCategory = (id: number) => {
    const next = new URLSearchParams(searchParams)
    if (id === categoryId) {
      next.delete('category_id')
    } else {
      next.set('category_id', String(id))
    }
    setSearchParams(next)
  }

  return (
    <div className="flex gap-4 items-start">
      <aside
        className="shrink-0 rounded bg-white"
        style={{ width: 200, minHeight: 420, padding: '12px 16px' }}
      >
        <div className="text-base font-bold mb-2" style={{ color: '#333' }}>
          商品分类
        </div>
        {tree.map((root) => (
          <div key={root.id} className="mb-3">
            <button
              type="button"
              onClick={() => pickCategory(root.id)}
              className="w-full text-left font-medium hover:opacity-80 cursor-pointer bg-transparent border-0 text-sm"
              style={{ color: categoryId === root.id ? '#F31947' : '#333' }}
            >
              {root.name}
            </button>
            {root.children?.map((child) => (
              <button
                key={child.id}
                type="button"
                onClick={() => pickCategory(child.id)}
                className="block w-full text-left pl-4 text-xs hover:opacity-80 cursor-pointer bg-transparent border-0"
                style={{ color: categoryId === child.id ? '#F31947' : '#666', marginTop: 4 }}
              >
                {child.name}
              </button>
            ))}
          </div>
        ))}
      </aside>

      <section className="flex-1 rounded bg-white" style={{ padding: '12px 16px', minHeight: 420 }}>
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
          {keyword && (
            <span className="text-xs ml-auto" style={{ color: '#999' }}>
              搜索「{keyword}」共 {total} 件商品
            </span>
          )}
        </div>

        <Spin spinning={loading}>
          {goods.length === 0 ? (
            <Empty description="暂无商品" style={{ marginTop: 80 }} />
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
