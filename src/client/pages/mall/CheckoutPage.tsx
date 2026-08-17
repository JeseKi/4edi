import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { App, Button, Checkbox, Empty, Form, Input, Modal, Radio, Spin } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import {
  createMallAddress,
  createMallOrder,
  listMallAddresses,
  listMallCart,
  listMyCoupons,
  previewMallOrder,
} from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen } from '../../lib/mallFormat'
import type { MallAddress, MallOrderPreview, MallUserCoupon } from '../../lib/types'

export default function CheckoutPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [form] = Form.useForm()

  const [addresses, setAddresses] = useState<MallAddress[]>([])
  const [selectedAddressId, setSelectedAddressId] = useState<number | null>(null)
  const [preview, setPreview] = useState<MallOrderPreview | null>(null)
  const [cartItemIds, setCartItemIds] = useState<number[]>([])
  const [coupons, setCoupons] = useState<MallUserCoupon[]>([])
  const [selectedCouponId, setSelectedCouponId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [addressModalOpen, setAddressModalOpen] = useState(false)
  const [savingAddress, setSavingAddress] = useState(false)

  const directSkuId = searchParams.get('sku_id')
  const directQuantity = Number(searchParams.get('quantity') ?? 1)
  const isDirectBuy = directSkuId !== null

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [addrList, couponResult] = await Promise.all([listMallAddresses(), listMyCoupons({ status: 'unused', page_size: 50 })])
      setAddresses(addrList)
      setCoupons(couponResult.items)
      setSelectedAddressId((current) => current ?? addrList.find((a) => a.is_default)?.id ?? addrList[0]?.id ?? null)

      let items: { sku_id: number; quantity: number }[]
      if (directSkuId) {
        items = [{ sku_id: Number(directSkuId), quantity: directQuantity }]
        setCartItemIds([])
      } else {
        const cartItems = await listMallCart()
        const selected = cartItems.filter((i) => i.selected)
        setCartItemIds(selected.map((i) => i.id))
        items = selected.map((i) => ({ sku_id: i.sku_id, quantity: i.quantity }))
      }
      if (items.length === 0) {
        setPreview(null)
        return
      }
      setPreview(await previewMallOrder(items))
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '结算信息加载失败'))
    } finally {
      setLoading(false)
    }
  }, [directSkuId, directQuantity, message])

  useEffect(() => {
    load()
  }, [load])

  const handleSelectCoupon = async (couponId: number | null) => {
    setSelectedCouponId(couponId)
    let items: { sku_id: number; quantity: number }[]
    if (directSkuId) {
      items = [{ sku_id: Number(directSkuId), quantity: directQuantity }]
    } else {
      const cartItems = await listMallCart()
      items = cartItems
        .filter((i) => i.selected)
        .map((i) => ({ sku_id: i.sku_id, quantity: i.quantity }))
    }
    if (items.length === 0) return
    try {
      setPreview(await previewMallOrder(items, couponId ?? undefined))
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '优惠券不可用'))
      setSelectedCouponId(null)
      setPreview(await previewMallOrder(items))
    }
  }

  const submitOrder = async () => {
    if (selectedAddressId == null) {
      message.warning('请选择收货地址')
      return
    }
    if (!preview) return
    setSubmitting(true)
    try {
      const items = preview.items.map((i) => ({ sku_id: i.sku_id, quantity: i.quantity }))
      const order = await createMallOrder({
        address_id: selectedAddressId,
        items,
        cart_item_ids: isDirectBuy ? undefined : cartItemIds,
        coupon_id: selectedCouponId ?? undefined,
      })
      message.success('订单提交成功')
      navigate(`/mall/orders/${order.order_no}`)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '下单失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const saveAddress = async () => {
    const values = await form.validateFields()
    setSavingAddress(true)
    try {
      const created = await createMallAddress(values)
      setAddresses((list) => [...list, created])
      setSelectedAddressId(created.id)
      setAddressModalOpen(false)
      form.resetFields()
      message.success('地址已保存')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '地址保存失败'))
    } finally {
      setSavingAddress(false)
    }
  }

  const selectedAddress = useMemo(
    () => addresses.find((a) => a.id === selectedAddressId) ?? null,
    [addresses, selectedAddressId],
  )

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    )
  }

  if (!preview) {
    return (
      <Empty description="没有待结算的商品" style={{ marginTop: 80 }}>
        <Button type="primary" onClick={() => navigate('/mall')} style={{ background: '#F31947' }}>
          去购物
        </Button>
      </Empty>
    )
  }

  return (
    <div className="space-y-4">
      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
          收货地址
        </h3>
        <div className="flex flex-wrap gap-3">
          {addresses.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => setSelectedAddressId(a.id)}
              className="text-left rounded px-4 py-3 cursor-pointer"
              style={{
                width: 280,
                border: selectedAddressId === a.id ? '1px solid #F31947' : '1px solid #e5e5e5',
                background: selectedAddressId === a.id ? '#fff7f8' : '#fff',
              }}
            >
              <div className="text-sm font-medium" style={{ color: '#333' }}>
                {a.receiver} <span className="font-normal text-xs ml-1">{a.phone}</span>
              </div>
              <div className="text-xs mt-1" style={{ color: '#666' }}>
                {a.province}
                {a.city}
                {a.district}
                {a.detail}
              </div>
              {a.is_default && (
                <div className="text-xs mt-1" style={{ color: '#F31947' }}>
                  默认地址
                </div>
              )}
            </button>
          ))}
          <button
            type="button"
            onClick={() => setAddressModalOpen(true)}
            className="rounded px-4 py-3 cursor-pointer flex flex-col items-center justify-center gap-1"
            style={{ width: 280, border: '1px dashed #ccc', color: '#999' }}
          >
            <PlusOutlined />
            <span className="text-xs">新增地址</span>
          </button>
        </div>
        {addresses.length > 0 && selectedAddress == null && (
          <div className="text-xs mt-2" style={{ color: '#F31947' }}>
            请选择一个收货地址
          </div>
        )}
      </section>

      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
          商品清单
        </h3>
        {preview.items.map((item) => (
          <div key={item.sku_id} className="flex items-center gap-3 py-2" style={{ borderBottom: '1px solid #f5f5f5' }}>
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
      </section>

      <section className="rounded bg-white" style={{ padding: '16px 20px' }}>
        <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
          优惠券
        </h3>
        {coupons.length === 0 ? (
          <div className="text-sm" style={{ color: '#999' }}>
            暂无可用优惠券
          </div>
        ) : (
          <Radio.Group
            value={selectedCouponId}
            onChange={(e) => handleSelectCoupon(e.target.value)}
            className="w-full"
          >
            <div className="space-y-2">
              <Radio value={null} className="w-full">
                <span className="text-sm" style={{ color: '#555' }}>
                  不使用优惠券
                </span>
              </Radio>
              {coupons.map((coupon) => (
                <Radio key={coupon.id} value={coupon.id} className="w-full">
                  <span className="text-sm" style={{ color: '#333' }}>
                    {coupon.name}
                    <span className="ml-2" style={{ color: '#F31947' }}>
                      {coupon.type === 'discount'
                        ? `${coupon.discount} 折`
                        : `减 ¥${formatFen(coupon.value_fen ?? 0)}`}
                    </span>
                    <span className="ml-2 text-xs" style={{ color: '#999' }}>
                      {coupon.min_amount_fen && coupon.min_amount_fen > 0
                        ? `满 ¥${formatFen(coupon.min_amount_fen)} 可用`
                        : '无门槛'}
                      {coupon.scope === 'shop' && coupon.shop_name ? ` · ${coupon.shop_name}` : ''}
                    </span>
                  </span>
                </Radio>
              ))}
            </div>
          </Radio.Group>
        )}
      </section>

      <section className="rounded bg-white text-right" style={{ padding: '16px 20px' }}>
        <div className="text-sm mb-1" style={{ color: '#666' }}>
          商品金额：¥{formatFen(preview.goods_amount_fen)}
        </div>
        <div className="text-sm mb-1" style={{ color: '#666' }}>
          运费：¥{formatFen(preview.freight_fen)}
        </div>
        {preview.coupon_discount_fen > 0 && (
          <div className="text-sm mb-1" style={{ color: '#F31947' }}>
            优惠券抵扣：-¥{formatFen(preview.coupon_discount_fen)}
          </div>
        )}
        <div className="text-base mb-4">
          应付总额：
          <span className="text-2xl font-bold" style={{ color: '#F31947' }}>
            ¥{formatFen(preview.pay_amount_fen)}
          </span>
        </div>
        <Button
          type="primary"
          size="large"
          loading={submitting}
          onClick={submitOrder}
          style={{ background: '#F31947', width: 160 }}
        >
          提交订单
        </Button>
      </section>

      <Modal
        title="新增收货地址"
        open={addressModalOpen}
        onCancel={() => setAddressModalOpen(false)}
        onOk={saveAddress}
        confirmLoading={savingAddress}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="receiver" label="收货人" rules={[{ required: true, message: '请输入收货人' }]}>
            <Input placeholder="姓名" maxLength={50} />
          </Form.Item>
          <Form.Item
            name="phone"
            label="手机号"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '手机号格式不正确' },
            ]}
          >
            <Input placeholder="11 位手机号" maxLength={20} />
          </Form.Item>
          <div className="flex gap-2">
            <Form.Item name="province" label="省份" className="flex-1" rules={[{ required: true }]}>
              <Input placeholder="如：广东省" maxLength={50} />
            </Form.Item>
            <Form.Item name="city" label="城市" className="flex-1" rules={[{ required: true }]}>
              <Input placeholder="如：深圳市" maxLength={50} />
            </Form.Item>
            <Form.Item name="district" label="区县" className="flex-1" rules={[{ required: true }]}>
              <Input placeholder="如：南山区" maxLength={50} />
            </Form.Item>
          </div>
          <Form.Item name="detail" label="详细地址" rules={[{ required: true, message: '请输入详细地址' }]}>
            <Input.TextArea rows={2} placeholder="街道、门牌号等" maxLength={200} />
          </Form.Item>
          <Form.Item name="is_default" valuePropName="checked">
            <Checkbox>设为默认地址</Checkbox>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
