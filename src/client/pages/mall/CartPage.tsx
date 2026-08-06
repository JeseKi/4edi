import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { App, Button, Checkbox, Empty, InputNumber, Spin } from 'antd'
import { DeleteOutlined } from '@ant-design/icons'
import {
  deleteMallCartItems,
  listMallCart,
  updateMallCartItem,
} from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen } from '../../lib/mallFormat'
import type { MallCartItem } from '../../lib/types'

export default function CartPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [items, setItems] = useState<MallCartItem[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listMallCart())
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '购物车加载失败'))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    load()
  }, [load])

  const selected = items.filter((i) => i.selected)
  const allSelected = items.length > 0 && selected.length === items.length
  const totalFen = selected.reduce((sum, i) => sum + i.subtotal_fen, 0)

  const toggleAll = (checked: boolean) => {
    Promise.all(items.map((i) => updateMallCartItem(i.id, { selected: checked }))).then(load)
  }

  const toggleOne = (item: MallCartItem, checked: boolean) => {
    updateMallCartItem(item.id, { selected: checked })
      .then(load)
      .catch((err) => message.error(resolveApiErrorMessage(err, '操作失败')))
  }

  const changeQuantity = (item: MallCartItem, quantity: number) => {
    if (quantity < 1) return
    updateMallCartItem(item.id, { quantity })
      .then(load)
      .catch((err) => message.error(resolveApiErrorMessage(err, '修改数量失败')))
  }

  const removeItems = (ids: number[]) => {
    deleteMallCartItems(ids)
      .then(load)
      .catch((err) => message.error(resolveApiErrorMessage(err, '删除失败')))
  }

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h2 className="text-base font-bold mb-4" style={{ color: '#333' }}>
        我的购物车
      </h2>
      {items.length === 0 ? (
        <Empty description="购物车是空的" style={{ marginTop: 60, marginBottom: 60 }}>
          <Button type="primary" onClick={() => navigate('/mall')} style={{ background: '#F31947' }}>
            去逛逛
          </Button>
        </Empty>
      ) : (
        <>
          <div className="flex items-center gap-4 pb-3 text-xs" style={{ color: '#999', borderBottom: '2px solid #f0f0f0' }}>
            <Checkbox checked={allSelected} onChange={(e) => toggleAll(e.target.checked)}>
              全选
            </Checkbox>
            <span className="flex-1">商品</span>
            <span style={{ width: 100, textAlign: 'center' }}>单价</span>
            <span style={{ width: 140, textAlign: 'center' }}>数量</span>
            <span style={{ width: 100, textAlign: 'center' }}>小计</span>
            <span style={{ width: 60, textAlign: 'center' }}>操作</span>
          </div>

          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-4 py-3"
              style={{ borderBottom: '1px solid #f5f5f5' }}
            >
              <Checkbox
                checked={item.selected}
                disabled={!item.goods_on}
                onChange={(e) => toggleOne(item, e.target.checked)}
              />
              <div
                className="flex items-center gap-3 flex-1 cursor-pointer"
                onClick={() => navigate(`/mall/goods/${item.goods_id}`)}
              >
                <img
                  src={item.goods_image}
                  alt={item.goods_name}
                  className="rounded"
                  style={{ width: 64, height: 64, objectFit: 'cover', background: '#f7f7f7' }}
                />
                <div>
                  <div className="text-sm" style={{ color: '#333' }}>
                    {item.goods_name}
                  </div>
                  <div className="text-xs mt-1" style={{ color: '#999' }}>
                    {Object.entries(item.sku_specs)
                      .map(([k, v]) => `${k}:${v}`)
                      .join(' · ')}
                  </div>
                  {!item.goods_on && (
                    <span className="text-xs mt-1 inline-block" style={{ color: '#F31947' }}>
                      商品已下架
                    </span>
                  )}
                </div>
              </div>
              <span style={{ width: 100, textAlign: 'center' }} className="text-sm">
                ¥{formatFen(item.price_fen)}
              </span>
              <div style={{ width: 140, display: 'flex', justifyContent: 'center' }}>
                <InputNumber
                  min={1}
                  max={item.stock}
                  value={item.quantity}
                  disabled={!item.goods_on}
                  onChange={(v) => changeQuantity(item, v ?? 1)}
                />
              </div>
              <span className="font-bold" style={{ width: 100, textAlign: 'center', color: '#F31947' }}>
                ¥{formatFen(item.subtotal_fen)}
              </span>
              <div style={{ width: 60, textAlign: 'center' }}>
                <Button
                  type="text"
                  danger
                  icon={<DeleteOutlined />}
                  onClick={() => removeItems([item.id])}
                />
              </div>
            </div>
          ))}

          <div className="flex items-center justify-end gap-6 mt-4">
            <span className="text-sm" style={{ color: '#999' }}>
              已选 {selected.length} 件
            </span>
            <span className="text-sm">
              合计：
              <span className="text-xl font-bold" style={{ color: '#F31947' }}>
                ¥{formatFen(totalFen)}
              </span>
            </span>
            <Button
              type="primary"
              size="large"
              disabled={selected.length === 0}
              onClick={() => navigate('/mall/checkout')}
              style={{ background: '#F31947', width: 120 }}
            >
              去结算
            </Button>
          </div>
        </>
      )}
    </div>
  )
}
