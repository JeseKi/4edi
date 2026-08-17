import { useCallback, useEffect, useState } from 'react'
import { App, Button, DatePicker, Empty, Form, Input, InputNumber, Modal, Pagination, Popconfirm, Radio, Spin, Tag } from 'antd'
import type { Dayjs } from 'dayjs'
import dayjs from 'dayjs'
import {
  createSellerCoupon,
  listSellerCoupons,
  setSellerCouponStatus,
  updateSellerCoupon,
} from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import { formatFen } from '../../../lib/mallFormat'
import type { MallCouponTemplate, MallCouponType } from '../../../lib/types'

const { RangePicker } = DatePicker

const TYPE_LABELS: Record<string, string> = { fixed: '满减券', discount: '折扣券' }
const STATUS_TAG_COLOR: Record<string, string> = {
  active: 'green',
  paused: 'orange',
  expired: 'default',
}
const STATUS_LABELS: Record<string, string> = {
  active: '进行中',
  paused: '已暂停',
  expired: '已过期',
}

interface FormValues {
  name: string
  type: MallCouponType
  value_fen?: number
  discount?: number
  min_amount_fen?: number
  total_count?: number
  per_user_limit?: number
  period: [Dayjs, Dayjs]
}

export default function CouponManagePage() {
  const { message } = App.useApp()
  const [form] = Form.useForm<FormValues>()
  const [items, setItems] = useState<MallCouponTemplate[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [modalOpen, setModalOpen] = useState(false)
  const [editing, setEditing] = useState<MallCouponTemplate | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [couponType, setCouponType] = useState<MallCouponType>('fixed')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listSellerCoupons({ page, page_size: 10 })
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '优惠券列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, message])

  useEffect(() => {
    load()
  }, [load])

  const openCreate = () => {
    setEditing(null)
    setCouponType('fixed')
    form.resetFields()
    form.setFieldsValue({ type: 'fixed', total_count: 0, per_user_limit: 1, min_amount_fen: 0, discount: 90 })
    setModalOpen(true)
  }

  const openEdit = (coupon: MallCouponTemplate) => {
    setEditing(coupon)
    setCouponType(coupon.type)
    form.resetFields()
    form.setFieldsValue({
      name: coupon.name,
      type: coupon.type,
      value_fen: coupon.value_fen,
      discount: coupon.discount,
      min_amount_fen: coupon.min_amount_fen,
      total_count: coupon.total_count,
      per_user_limit: coupon.per_user_limit,
      period: [dayjs(coupon.valid_from), dayjs(coupon.valid_until)],
    })
    setModalOpen(true)
  }

  const submit = async () => {
    const values = await form.validateFields()
    if (!values.period || values.period.length !== 2) {
      message.warning('请选择有效期')
      return
    }
    const payload = {
      name: values.name,
      type: values.type,
      value_fen: values.value_fen ?? 0,
      discount: values.discount ?? 100,
      min_amount_fen: values.min_amount_fen ?? 0,
      total_count: values.total_count ?? 0,
      per_user_limit: values.per_user_limit ?? 1,
      valid_from: values.period[0].toISOString(),
      valid_until: values.period[1].toISOString(),
    }
    setSubmitting(true)
    try {
      if (editing) {
        await updateSellerCoupon(editing.id, payload)
        message.success('优惠券已更新')
      } else {
        await createSellerCoupon(payload)
        message.success('优惠券已创建')
      }
      setModalOpen(false)
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, editing ? '更新失败' : '创建失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const toggleStatus = async (coupon: MallCouponTemplate, on: boolean) => {
    try {
      await setSellerCouponStatus(coupon.id, on)
      message.success(on ? '已上架' : '已下架')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    }
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-base font-bold" style={{ color: '#333' }}>
          优惠券管理
        </h3>
        <Button type="primary" style={{ background: '#F31947' }} onClick={openCreate}>
          新建优惠券
        </Button>
      </div>

      <Spin spinning={loading}>
        {items.length === 0 ? (
          <Empty description="暂无优惠券" style={{ marginTop: 48 }} />
        ) : (
          <div className="space-y-3">
            {items.map((coupon) => (
              <div
                key={coupon.id}
                className="flex items-center rounded px-4 py-3"
                style={{ border: '1px solid #f0f0f0' }}
              >
                <div
                  className="flex flex-col items-center justify-center shrink-0 rounded"
                  style={{ width: 110, height: 64, background: '#fff7f8', color: '#F31947' }}
                >
                  <span className="text-xl font-bold">
                    {coupon.type === 'discount' ? `${coupon.discount} 折` : `¥${formatFen(coupon.value_fen)}`}
                  </span>
                  <span className="text-xs mt-0.5">
                    {coupon.min_amount_fen > 0 ? `满 ¥${formatFen(coupon.min_amount_fen)} 可用` : '无门槛'}
                  </span>
                </div>
                <div className="flex-1 ml-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium" style={{ color: '#333' }}>
                      {coupon.name}
                    </span>
                    <Tag color={STATUS_TAG_COLOR[coupon.status]}>{STATUS_LABELS[coupon.status]}</Tag>
                  </div>
                  <div className="text-xs mt-1" style={{ color: '#999' }}>
                    {TYPE_LABELS[coupon.type]} ·{' '}
                    {coupon.total_count > 0
                      ? `已领 ${coupon.received_count}/${coupon.total_count}`
                      : '不限量'}{' '}
                    · 每人限领 {coupon.per_user_limit} 张 · 有效期至 {coupon.valid_until.slice(0, 10)}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button size="small" onClick={() => openEdit(coupon)}>
                    编辑
                  </Button>
                  {coupon.status === 'active' ? (
                    <Popconfirm title="下架后用户将无法领取，确定下架？" onConfirm={() => toggleStatus(coupon, false)}>
                      <Button size="small">下架</Button>
                    </Popconfirm>
                  ) : (
                    coupon.status === 'paused' && (
                      <Button size="small" type="primary" style={{ background: '#F31947' }} onClick={() => toggleStatus(coupon, true)}>
                        上架
                      </Button>
                    )
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Spin>

      {total > 10 && (
        <div className="flex justify-center mt-4">
          <Pagination current={page} pageSize={10} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}

      <Modal
        title={editing ? '编辑优惠券' : '新建优惠券'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={submit}
        confirmLoading={submitting}
        okText="保存"
        cancelText="取消"
        width={520}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="name" label="券名称" rules={[{ required: true, message: '请输入券名称' }, { max: 100 }]}>
            <Input placeholder="如：满 100 减 20" />
          </Form.Item>
          <Form.Item name="type" label="券类型" rules={[{ required: true }]}>
            <Radio.Group
              onChange={(e) => setCouponType(e.target.value)}
              options={[
                { label: '满减券', value: 'fixed' },
                { label: '折扣券', value: 'discount' },
              ]}
            />
          </Form.Item>
          {couponType === 'fixed' ? (
            <Form.Item name="value_fen" label="面额（分）" rules={[{ required: true, message: '请输入面额' }]}>
              <InputNumber min={1} style={{ width: '100%' }} placeholder="如：2000 = 减 20 元" />
            </Form.Item>
          ) : (
            <Form.Item name="discount" label="折扣（1-99，90 = 9 折）" rules={[{ required: true }]}>
              <InputNumber min={1} max={99} style={{ width: '100%' }} />
            </Form.Item>
          )}
          <div className="flex gap-3">
            <Form.Item name="min_amount_fen" label="使用门槛（分，0 = 无门槛）" className="flex-1">
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="total_count" label="发行量（0 = 不限）" className="flex-1">
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <div className="flex gap-3">
            <Form.Item name="per_user_limit" label="每人限领" className="flex-1">
              <InputNumber min={1} max={100} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item name="period" label="有效期" className="flex-1" rules={[{ required: true, message: '请选择有效期' }]}>
              <RangePicker showTime style={{ width: '100%' }} />
            </Form.Item>
          </div>
        </Form>
      </Modal>
    </div>
  )
}
