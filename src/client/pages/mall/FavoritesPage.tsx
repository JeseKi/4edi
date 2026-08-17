import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { App, Button, Empty, Pagination, Spin, Tabs } from 'antd'
import { HeartFilled, ShopOutlined } from '@ant-design/icons'
import { listMyFavorites, removeMallFavorite } from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen } from '../../lib/mallFormat'
import type { MallFavorite, MallFavoriteTargetType } from '../../lib/types'

export default function FavoritesPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<MallFavoriteTargetType>('goods')
  const [items, setItems] = useState<MallFavorite[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listMyFavorites({ target_type: activeTab, page, page_size: 12 })
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '收藏列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [activeTab, page, message])

  useEffect(() => {
    load()
  }, [load])

  const handleRemove = async (favorite: MallFavorite) => {
    try {
      await removeMallFavorite(favorite.target_type, favorite.target_id)
      message.success('已取消收藏')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '取消收藏失败'))
    }
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        我的收藏
      </h3>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => {
          setActiveTab(key as MallFavoriteTargetType)
          setPage(1)
        }}
        items={[
          { key: 'goods', label: '收藏商品' },
          { key: 'shop', label: '关注店铺' },
        ]}
      />

      <Spin spinning={loading}>
        {items.length === 0 ? (
          <Empty description={activeTab === 'goods' ? '暂无收藏商品' : '暂未关注店铺'} style={{ marginTop: 48 }} />
        ) : (
          <div className="grid gap-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
            {items.map((favorite) =>
              activeTab === 'goods' ? (
                <div
                  key={favorite.id}
                  className="rounded cursor-pointer"
                  style={{ border: '1px solid #f0f0f0', overflow: 'hidden', background: '#fff' }}
                  onClick={() => navigate(`/mall/goods/${favorite.target_id}`)}
                >
                  {favorite.target_image ? (
                    <img
                      src={favorite.target_image}
                      alt={favorite.target_name ?? '商品'}
                      className="w-full"
                      style={{ height: 160, objectFit: 'cover', background: '#fafafa' }}
                    />
                  ) : (
                    <div className="w-full flex items-center justify-center" style={{ height: 160, background: '#fafafa' }}>
                      <ShopOutlined style={{ fontSize: 40, color: '#ddd' }} />
                    </div>
                  )}
                  <div className="p-3">
                    <div className="text-sm truncate" style={{ color: '#333' }}>
                      {favorite.target_name ?? '商品已下架'}
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-base font-bold" style={{ color: '#F31947' }}>
                        {favorite.target_price_fen != null ? `¥${formatFen(favorite.target_price_fen)}` : '—'}
                      </span>
                      <Button
                        size="small"
                        icon={<HeartFilled style={{ color: '#F31947' }} />}
                        onClick={(event) => {
                          event.stopPropagation()
                          handleRemove(favorite)
                        }}
                      >
                        取消收藏
                      </Button>
                    </div>
                  </div>
                </div>
              ) : (
                <div
                  key={favorite.id}
                  className="rounded p-4 cursor-pointer"
                  style={{ border: '1px solid #f0f0f0', background: '#fff' }}
                  onClick={() => navigate(`/mall/goods?shop_id=${favorite.target_id}`)}
                >
                  <div className="flex items-center gap-3">
                    {favorite.target_image ? (
                      <img
                        src={favorite.target_image}
                        alt={favorite.target_name ?? '店铺'}
                        className="rounded-full"
                        style={{ width: 48, height: 48, objectFit: 'cover' }}
                      />
                    ) : (
                      <div
                        className="rounded-full flex items-center justify-center"
                        style={{ width: 48, height: 48, background: '#fafafa' }}
                      >
                        <ShopOutlined style={{ fontSize: 20, color: '#bbb' }} />
                      </div>
                    )}
                    <div className="flex-1">
                      <div className="text-sm font-medium truncate" style={{ color: '#333' }}>
                        {favorite.target_name ?? '店铺已关闭'}
                      </div>
                    </div>
                  </div>
                  <Button
                    size="small"
                    className="mt-3 w-full"
                    onClick={(event) => {
                      event.stopPropagation()
                      handleRemove(favorite)
                    }}
                  >
                    取消关注
                  </Button>
                </div>
              ),
            )}
          </div>
        )}
      </Spin>

      {total > 12 && (
        <div className="flex justify-center mt-4">
          <Pagination current={page} pageSize={12} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}
    </div>
  )
}
