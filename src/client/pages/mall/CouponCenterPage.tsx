import { useCallback, useEffect, useState } from 'react'
import { App, Button, Empty, Pagination, Spin, Tabs, Tag } from 'antd'
import { listAvailableCoupons, listMyCoupons, receiveCoupon } from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import { formatFen } from '../../lib/mallFormat'
import type { MallCouponTemplate, MallUserCoupon } from '../../lib/types'

const SCOPE_LABELS: Record<string, string> = { platform: '平台券', shop: '店铺券' }
const STATUS_TAG_COLOR: Record<string, string> = {
  unused: 'green',
  used: 'default',
  expired: 'default',
}

function couponValueText(coupon: MallCouponTemplate | MallUserCoupon): string {
  if (coupon.type === 'discount') {
    return `${coupon.discount ?? 100} 折`
  }
  return `¥${formatFen(coupon.value_fen ?? 0)}`
}

function couponConditionText(coupon: MallCouponTemplate | MallUserCoupon): string {
  const min = coupon.min_amount_fen ?? 0
  return min > 0 ? `满 ¥${formatFen(min)} 可用` : '无门槛'
}

export default function CouponCenterPage() {
  const { message } = App.useApp()
  const [activeTab, setActiveTab] = useState('center')
  const [centerItems, setCenterItems] = useState<MallCouponTemplate[]>([])
  const [centerTotal, setCenterTotal] = useState(0)
  const [centerPage, setCenterPage] = useState(1)
  const [myStatus, setMyStatus] = useState<string | undefined>(undefined)
  const [myItems, setMyItems] = useState<MallUserCoupon[]>([])
  const [myTotal, setMyTotal] = useState(0)
  const [myPage, setMyPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [receivingId, setReceivingId] = useState<number | null>(null)

  const loadCenter = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listAvailableCoupons({ page: centerPage, page_size: 10 })
      setCenterItems(result.items)
      setCenterTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '领券中心加载失败'))
    } finally {
      setLoading(false)
    }
  }, [centerPage, message])

  const loadMine = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listMyCoupons({ status: myStatus as never, page: myPage, page_size: 10 })
      setMyItems(result.items)
      setMyTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '我的优惠券加载失败'))
    } finally {
      setLoading(false)
    }
  }, [myStatus, myPage, message])

  useEffect(() => {
    if (activeTab === 'center') loadCenter()
    else loadMine()
  }, [activeTab, loadCenter, loadMine])

  const handleReceive = async (couponId: number) => {
    setReceivingId(couponId)
    try {
      await receiveCoupon(couponId)
      message.success('领取成功，可在「我的优惠券」中查看')
      loadCenter()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '领取失败'))
    } finally {
      setReceivingId(null)
    }
  }

  const renderCouponCard = (
    coupon: MallCouponTemplate | MallUserCoupon,
    footer?: React.ReactNode,
  ) => (
    <div
      key={`${'coupon_id' in coupon ? coupon.coupon_id : coupon.id}-${'status' in coupon ? coupon.status : 'tpl'}`}
      className="flex items-center rounded px-4 py-3"
      style={{ border: '1px solid #f0f0f0', background: '#fff' }}
    >
      <div
        className="flex flex-col items-center justify-center shrink-0 rounded"
        style={{ width: 110, height: 64, background: '#fff7f8', color: '#F31947' }}
      >
        <span className="text-xl font-bold">{couponValueText(coupon)}</span>
        <span className="text-xs mt-0.5">{couponConditionText(coupon)}</span>
      </div>
      <div className="flex-1 ml-4">
        <div className="text-sm font-medium" style={{ color: '#333' }}>
          {coupon.name}
        </div>
        <div className="text-xs mt-1" style={{ color: '#999' }}>
          {SCOPE_LABELS[coupon.scope ?? 'platform']}
          {coupon.scope === 'shop' && coupon.shop_name ? ` · ${coupon.shop_name}` : ''} · 有效期至{' '}
          {coupon.valid_until?.slice(0, 10)}
        </div>
        {'total_count' in coupon && coupon.total_count > 0 && (
          <div className="text-xs mt-0.5" style={{ color: '#999' }}>
            剩余 {Math.max(coupon.total_count - coupon.received_count, 0)} 张
          </div>
        )}
      </div>
      {footer}
    </div>
  )

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        优惠券
      </h3>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'center', label: '领券中心' },
          { key: 'mine', label: '我的优惠券' },
        ]}
      />

      <Spin spinning={loading}>
        {activeTab === 'center' ? (
          centerItems.length === 0 ? (
            <Empty description="暂无可用优惠券" style={{ marginTop: 48 }} />
          ) : (
            <div className="space-y-3">
              {centerItems.map((coupon) =>
                renderCouponCard(
                  coupon,
                  <Button
                    type="primary"
                    size="small"
                    loading={receivingId === coupon.id}
                    style={{ background: '#F31947' }}
                    onClick={() => handleReceive(coupon.id)}
                  >
                    领取
                  </Button>,
                ),
              )}
            </div>
          )
        ) : (
          <>
            <div className="flex gap-2 mb-3">
              {[
                { key: undefined, label: '全部' },
                { key: 'unused', label: '未使用' },
                { key: 'used', label: '已使用' },
                { key: 'expired', label: '已过期' },
              ].map((tab) => (
                <Tag
                  key={tab.key ?? 'all'}
                  color={myStatus === tab.key ? '#F31947' : undefined}
                  className="cursor-pointer px-3 py-1"
                  onClick={() => {
                    setMyStatus(tab.key)
                    setMyPage(1)
                  }}
                >
                  {tab.label}
                </Tag>
              ))}
            </div>
            {myItems.length === 0 ? (
              <Empty description="暂无优惠券" style={{ marginTop: 48 }} />
            ) : (
              <div className="space-y-3">
                {myItems.map((coupon) =>
                  renderCouponCard(
                    coupon,
                    <Tag color={STATUS_TAG_COLOR[coupon.status]}>
                      {coupon.status === 'unused'
                        ? '未使用'
                        : coupon.status === 'used'
                          ? `已使用${coupon.order_no ? `（${coupon.order_no}）` : ''}`
                          : '已过期'}
                    </Tag>,
                  ),
                )}
              </div>
            )}
            {myTotal > 10 && (
              <div className="flex justify-center mt-4">
                <Pagination current={myPage} pageSize={10} total={myTotal} onChange={setMyPage} showSizeChanger={false} />
              </div>
            )}
          </>
        )}
      </Spin>

      {activeTab === 'center' && centerTotal > 10 && (
        <div className="flex justify-center mt-4">
          <Pagination current={centerPage} pageSize={10} total={centerTotal} onChange={setCenterPage} showSizeChanger={false} />
        </div>
      )}
    </div>
  )
}
