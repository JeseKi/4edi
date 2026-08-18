import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { App, Button, Divider, Empty, InputNumber, Pagination, Rate, Spin, Tag } from 'antd'
import { HeartFilled, HeartOutlined, ShoppingCartOutlined } from '@ant-design/icons'
import {
  addMallCartItem,
  addMallFavorite,
  getMallFavoriteStatus,
  getMallGoodsDetail,
  listGoodsEvaluations,
  recordMallFootprint,
  removeMallFavorite,
} from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen } from '../../lib/mallFormat'
import type { GoodsEvaluationList, MallGoodsDetail, MallGoodsSku } from '../../lib/types'
import { useAuth } from '../../hooks/useAuth'

export default function GoodsDetailPage() {
  const { goodsId } = useParams<{ goodsId: string }>()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const { message } = App.useApp()
  const [goods, setGoods] = useState<MallGoodsDetail | null>(null)
  const [selectedImage, setSelectedImage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedSku, setSelectedSku] = useState<MallGoodsSku | null>(null)
  const [quantity, setQuantity] = useState(1)
  const [evaluations, setEvaluations] = useState<GoodsEvaluationList | null>(null)
  const [evalLoading, setEvalLoading] = useState(false)
  const [evalPage, setEvalPage] = useState(1)
  const [favorited, setFavorited] = useState(false)

  const goodsIdNum = Number(goodsId)

  useEffect(() => {
    setLoading(true)
    getMallGoodsDetail(goodsIdNum)
      .then((detail) => {
        setGoods(detail)
        setSelectedImage(detail.main_image)
        if (detail.skus.length === 1) setSelectedSku(detail.skus[0])
      })
      .catch((err) => message.error(resolveApiErrorMessage(err, '商品加载失败')))
      .finally(() => setLoading(false))
  }, [goodsIdNum, message])

  useEffect(() => {
    setEvalLoading(true)
    listGoodsEvaluations(goodsIdNum, { page: evalPage, page_size: 5 })
      .then(setEvaluations)
      .catch((err) => message.error(resolveApiErrorMessage(err, '评价加载失败')))
      .finally(() => setEvalLoading(false))
  }, [goodsIdNum, evalPage, message])

  // 登录后：查询收藏状态 + 静默记录浏览足迹
  useEffect(() => {
    if (!isAuthenticated || !goods) return
    getMallFavoriteStatus('goods', goods.id)
      .then(({ favorited: f }) => setFavorited(f))
      .catch(() => {})
    recordMallFootprint(goods.id).catch(() => {})
  }, [isAuthenticated, goods, message])

  const specGroups = useMemo(() => {
    if (!goods) return []
    const groups = new Map<string, Set<string>>()
    for (const sku of goods.skus) {
      for (const [name, value] of Object.entries(sku.specs)) {
        if (!groups.has(name)) groups.set(name, new Set())
        groups.get(name)!.add(value)
      }
    }
    return [...groups.entries()].map(([name, values]) => ({ name, values: [...values] }))
  }, [goods])

  const selectSku = (specs: Record<string, string>) => {
    if (!goods) return
    const match = goods.skus.find((sku) => {
      const skuSpecs = sku.specs
      return Object.entries(specs).every(([k, v]) => skuSpecs[k] === v)
    })
    setSelectedSku(match ?? null)
  }

  const handleAddCart = async () => {
    if (!goods || !selectedSku) {
      message.warning('请选择商品规格')
      return
    }
    if (!isAuthenticated) {
      navigate('/login', { state: { from: location.pathname } })
      return
    }
    try {
      await addMallCartItem({ goods_id: goods.id, sku_id: selectedSku.id, quantity })
      message.success('已加入购物车')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '加入购物车失败'))
    }
  }

  const handleBuyNow = async () => {
    if (!goods || !selectedSku) {
      message.warning('请选择商品规格')
      return
    }
    if (!isAuthenticated) {
      navigate('/login', { state: { from: location.pathname } })
      return
    }
    navigate(`/mall/checkout?sku_id=${selectedSku.id}&quantity=${quantity}`)
  }

  const handleToggleFavorite = async () => {
    if (!goods) return
    if (!isAuthenticated) {
      navigate('/login', { state: { from: location.pathname } })
      return
    }
    try {
      if (favorited) {
        await removeMallFavorite('goods', goods.id)
        setFavorited(false)
        message.success('已取消收藏')
      } else {
        await addMallFavorite({ target_type: 'goods', target_id: goods.id })
        setFavorited(true)
        message.success('收藏成功')
      }
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    )
  }

  if (!goods) {
    return <Empty description="商品不存在或已下架" style={{ marginTop: 80 }} />
  }

  return (
    <>
      <div className="flex gap-6 items-start">
      <div className="shrink-0" style={{ width: 420 }}>
        <div
          className="rounded bg-white flex items-center justify-center overflow-hidden"
          style={{ width: 420, height: 420, border: '1px solid #f0f0f0' }}
        >
          <img
            src={selectedImage ?? goods.main_image}
            alt={goods.name}
            className="w-full h-full object-cover"
          />
        </div>
        {goods.images.length > 1 && (
          <div className="flex gap-2 mt-3 overflow-x-auto pb-1">
            {goods.images.map((url, index) => {
              const active = (selectedImage ?? goods.main_image) === url
              return (
                <button
                  key={`${url}-${index}`}
                  type="button"
                  aria-label={`查看商品图片 ${index + 1}`}
                  onClick={() => setSelectedImage(url)}
                  className="shrink-0 rounded overflow-hidden cursor-pointer bg-white"
                  style={{
                    width: 68,
                    height: 68,
                    border: active ? '2px solid #F31947' : '1px solid #e5e5e5',
                  }}
                >
                  <img src={url} alt="" className="w-full h-full object-cover" />
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="flex-1 bg-white rounded" style={{ padding: '24px 28px' }}>
        <h1 className="text-lg font-bold mb-1" style={{ color: '#222' }}>
          {goods.name}
        </h1>
        <div className="text-xs mb-4" style={{ color: '#999' }}>
          已售 {goods.sales} 件 · 库存 {goods.stock} 件
        </div>

        <div
          className="rounded mb-4"
          style={{ background: '#fff7f8', padding: '12px 16px', border: '1px solid #ffe1e5' }}
        >
          <span className="text-sm mr-2" style={{ color: '#999' }}>
            价格
          </span>
          <span className="text-2xl font-bold" style={{ color: '#F31947' }}>
            ¥{formatFen(selectedSku?.price_fen ?? goods.price_fen)}
          </span>
          {goods.original_price_fen != null && (
            <span className="text-xs line-through ml-2" style={{ color: '#999' }}>
              ¥{formatFen(goods.original_price_fen)}
            </span>
          )}
        </div>

        {specGroups.map((group) => (
          <div key={group.name} className="mb-3 flex items-start gap-3">
            <span className="text-sm shrink-0 pt-1" style={{ color: '#999', width: 56 }}>
              {group.name}
            </span>
            <div className="flex flex-wrap gap-2">
              {group.values.map((value) => {
                const specs = { [group.name]: value }
                const active = selectedSku?.specs[group.name] === value
                return (
                  <button
                    key={value}
                    type="button"
                    onClick={() => selectSku(specs)}
                    className="px-3 py-1 rounded text-sm cursor-pointer"
                    style={{
                      border: active ? '1px solid #F31947' : '1px solid #ddd',
                      color: active ? '#F31947' : '#555',
                      background: active ? '#fff5f6' : '#fff',
                    }}
                  >
                    {value}
                  </button>
                )
              })}
            </div>
          </div>
        ))}

        <div className="mb-5 flex items-center gap-3">
          <span className="text-sm" style={{ color: '#999' }}>
            数量
          </span>
          <InputNumber
            min={1}
            max={selectedSku?.stock ?? goods.stock}
            value={quantity}
            onChange={(v) => setQuantity(v ?? 1)}
          />
          {selectedSku && (
            <span className="text-xs" style={{ color: '#999' }}>
              该规格库存 {selectedSku.stock} 件
            </span>
          )}
        </div>

        {goods.status === 'on' ? (
          <div className="flex gap-3">
            <Button
              size="large"
              icon={<ShoppingCartOutlined />}
              onClick={handleAddCart}
              style={{ borderColor: '#F31947', color: '#F31947' }}
            >
              加入购物车
            </Button>
            <Button size="large" type="primary" onClick={handleBuyNow} style={{ background: '#F31947' }}>
              立即购买
            </Button>
            <Button
              size="large"
              icon={favorited ? <HeartFilled style={{ color: '#F31947' }} /> : <HeartOutlined />}
              onClick={handleToggleFavorite}
            >
              {favorited ? '已收藏' : '收藏'}
            </Button>
          </div>
        ) : (
          <Tag color="default" className="py-1 px-3">
            商品已下架
          </Tag>
        )}

        <Divider />
        <div className="text-sm" style={{ color: '#333', fontWeight: 500 }}>
          店铺：{goods.shop.name}
        </div>
      </div>
      </div>

      <section className="rounded bg-white mt-4" style={{ padding: '20px 24px' }}>
        <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
          商品详情
        </h3>
        <div
          className="text-sm"
          style={{ color: '#666', lineHeight: 1.8, whiteSpace: 'pre-line' }}
        >
          {goods.detail ?? '暂无商品详情'}
        </div>
      </section>

      <section className="rounded bg-white mt-4 flex-1" style={{ padding: '20px 24px' }}>
        <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
          商品评价
        </h3>
        <Spin spinning={evalLoading}>
          {evaluations && evaluations.summary.rating_count > 0 && (
            <div className="flex items-center gap-4 rounded px-4 py-3 mb-4" style={{ background: '#fafafa' }}>
              <div className="text-center">
                <div className="text-3xl font-bold" style={{ color: '#F31947' }}>
                  {evaluations.summary.avg_rating}
                </div>
                <Rate disabled value={evaluations.summary.avg_rating} allowHalf style={{ fontSize: 12 }} />
              </div>
              <div className="text-xs" style={{ color: '#999' }}>
                <div>共 {evaluations.summary.rating_count} 条评价</div>
                <div className="mt-1">好评率 {evaluations.summary.good_rate}%</div>
              </div>
            </div>
          )}

          {evaluations && evaluations.items.length === 0 ? (
            <Empty description="暂无评价" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ margin: '32px 0' }} />
          ) : (
            <div className="space-y-4">
              {evaluations?.items.map((evaluation) => (
                <div key={evaluation.id} style={{ borderBottom: '1px solid #f5f5f5', paddingBottom: 12 }}>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: '#333' }}>
                      {evaluation.buyer_username ?? `用户 ${evaluation.buyer_id}`}
                    </span>
                    <Rate disabled value={evaluation.rating} style={{ fontSize: 12 }} />
                    <span className="text-xs" style={{ color: '#999' }}>
                      {evaluation.created_at}
                    </span>
                  </div>
                  <div className="text-sm mt-2" style={{ color: '#555' }}>
                    {evaluation.content}
                  </div>
                  {evaluation.images.length > 0 && (
                    <div className="mt-2 flex gap-2">
                      {evaluation.images.map((url, index) => (
                        <img
                          key={`${url}-${index}`}
                          src={url}
                          alt="晒图"
                          className="rounded"
                          style={{ width: 64, height: 64, objectFit: 'cover' }}
                        />
                      ))}
                    </div>
                  )}
                  {evaluation.seller_reply && (
                    <div className="text-xs mt-2 rounded px-3 py-2" style={{ background: '#fafafa', color: '#888' }}>
                      卖家回复：{evaluation.seller_reply}
                    </div>
                  )}
                  {evaluation.append_content && (
                    <div className="text-sm mt-2" style={{ color: '#777' }}>
                      追评：{evaluation.append_content}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </Spin>
        {evaluations && evaluations.summary.total > 5 && (
          <div className="flex justify-center mt-4">
            <Pagination
              current={evalPage}
              pageSize={5}
              total={evaluations.summary.total}
              onChange={setEvalPage}
              showSizeChanger={false}
              size="small"
            />
          </div>
        )}
      </section>
    </>
  )
}
