import { useCallback, useEffect, useState } from 'react'
import { App, Button, Form, Input, InputNumber, Modal, Popconfirm, Select, Space, Table, Tag } from 'antd'
import { PlusOutlined } from '@ant-design/icons'
import {
  createSellerGoods,
  deleteSellerGoods,
  getSellerGoods,
  listSellerGoods,
  setSellerGoodsStatus,
  updateSellerGoods,
} from '../../../lib/sellerMall'
import type { MallSkuPayload } from '../../../lib/sellerMall'
import { listMallCategories } from '../../../lib/mall'
import { resolveApiErrorMessage } from '../../../lib/error'
import { formatFen } from '../../../lib/mallFormat'
import type { MallCategory, MallGoods } from '../../../lib/types'

interface SkuFormRow {
  key: string
  specs: string
  price_fen: number
  stock: number
}

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  draft: { text: '草稿', color: 'default' },
  on: { text: '在售', color: 'green' },
  off: { text: '已下架', color: 'orange' },
}

export default function SellerGoodsPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [goods, setGoods] = useState<MallGoods[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [categories, setCategories] = useState<MallCategory[]>([])
  const [editOpen, setEditOpen] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [skus, setSkus] = useState<SkuFormRow[]>([])
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listSellerGoods({ page, page_size: 10 })
      setGoods(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '商品加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, message])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    listMallCategories().then(setCategories).catch(() => {})
  }, [])

  const openCreate = () => {
    setEditingId(null)
    setSkus([])
    form.resetFields()
    setEditOpen(true)
  }

  const openEdit = async (record: MallGoods) => {
    setEditingId(record.id)
    form.resetFields()
    setSkus([])
    setEditOpen(true)
    try {
      const detail = await getSellerGoods(record.id)
      form.setFieldsValue({
        category_id: detail.category_id,
        name: detail.name,
        main_image: detail.main_image,
        detail: detail.detail,
        original_price_fen: detail.original_price_fen,
      })
      setSkus(
        detail.skus.map((sku, index) => ({
          key: String(sku.id ?? index),
          specs: Object.entries(sku.specs)
            .map(([k, v]) => `${k}:${v}`)
            .join('; '),
          price_fen: sku.price_fen,
          stock: sku.stock,
        })),
      )
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '商品详情加载失败'))
    }
  }

  const parseSkus = (rows: SkuFormRow[]): MallSkuPayload[] => {
    return rows.map((row) => {
      const specs: Record<string, string> = {}
      for (const part of row.specs.split(';')) {
        const [k, ...rest] = part.split(':')
        if (k?.trim()) specs[k.trim()] = rest.join(':').trim()
      }
      return { specs, price_fen: row.price_fen, stock: row.stock }
    })
  }

  const saveGoods = async () => {
    const values = await form.validateFields()
    if (skus.length === 0) {
      message.warning('请至少添加一个规格')
      return
    }
    setSaving(true)
    try {
      const payload = {
        category_id: values.category_id ?? null,
        name: values.name,
        main_image: values.main_image,
        detail: values.detail ?? null,
        original_price_fen: values.original_price_fen ?? null,
        skus: parseSkus(skus),
      }
      if (editingId == null) {
        await createSellerGoods(payload)
        message.success('商品已创建')
      } else {
        await updateSellerGoods(editingId, payload)
        message.success('商品已更新')
      }
      setEditOpen(false)
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  const toggleStatus = async (record: MallGoods, on: boolean) => {
    try {
      await setSellerGoodsStatus(record.id, on)
      message.success(on ? '商品已上架' : '商品已下架')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    }
  }

  const removeGoods = async (record: MallGoods) => {
    try {
      await deleteSellerGoods(record.id)
      message.success('商品已删除')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '删除失败'))
    }
  }

  const columns = [
    {
      title: '商品',
      dataIndex: 'name',
      key: 'name',
      render: (_: string, record: MallGoods) => (
        <div className="flex items-center gap-3">
          <img src={record.main_image} alt="" style={{ width: 48, height: 48, objectFit: 'cover', background: '#f7f7f7' }} />
          <span>{record.name}</span>
        </div>
      ),
    },
    {
      title: '价格',
      dataIndex: 'price_fen',
      key: 'price_fen',
      render: (fen: number) => <span style={{ color: '#F31947' }}>¥{formatFen(fen)}</span>,
    },
    { title: '库存', dataIndex: 'stock', key: 'stock' },
    { title: '销量', dataIndex: 'sales', key: 'sales' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: MallGoods['status']) => {
        const label = STATUS_LABELS[s]
        return <Tag color={label?.color}>{label?.text ?? s}</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: MallGoods) => (
        <Space>
          <Button size="small" onClick={() => openEdit(record)}>
            编辑
          </Button>
          {record.status === 'on' ? (
            <Button size="small" onClick={() => toggleStatus(record, false)}>
              下架
            </Button>
          ) : (
            <Button size="small" type="primary" ghost onClick={() => toggleStatus(record, true)}>
              上架
            </Button>
          )}
          <Popconfirm title="确定删除该商品？" onConfirm={() => removeGoods(record)}>
            <Button size="small" danger>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold" style={{ color: '#333' }}>
          商品管理
        </h3>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate} style={{ background: '#F31947' }}>
          新建商品
        </Button>
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={goods}
        loading={loading}
        pagination={{ current: page, pageSize: 10, total, onChange: setPage, showSizeChanger: false }}
      />

      <Modal
        title={editingId == null ? '新建商品' : '编辑商品'}
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={saveGoods}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
        width={640}
      >
        <Form form={form} layout="vertical" className="mt-4">
          <Form.Item name="name" label="商品名称" rules={[{ required: true, message: '请输入商品名称' }, { max: 120 }]}>
            <Input placeholder="商品名称" />
          </Form.Item>
          <Form.Item name="category_id" label="商品分类">
            <Select
              allowClear
              placeholder="选择分类"
              options={categories.map((c) => ({ label: c.name, value: c.id }))}
            />
          </Form.Item>
          <Form.Item
            name="main_image"
            label="主图地址"
            rules={[{ required: true, message: '请输入主图地址' }]}
            extra="可使用 /mall/goods-1.svg 等内置占位图"
          >
            <Input placeholder="/mall/goods-1.svg" />
          </Form.Item>
          <Form.Item name="detail" label="商品详情">
            <Input.TextArea rows={3} placeholder="商品描述" maxLength={2000} />
          </Form.Item>
          <Form.Item name="original_price_fen" label="划线价（分）">
            <InputNumber min={0} style={{ width: '100%' }} placeholder="如 39900" />
          </Form.Item>

          <div className="text-sm font-medium mb-2" style={{ color: '#333' }}>
            规格（格式：颜色:红色; 尺码:41）
          </div>
          {skus.length > 0 && (
            <div className="grid grid-cols-[2fr_1fr_1fr_auto] gap-2 mb-1 px-1 text-xs" style={{ color: '#666' }}>
              <span>规格</span>
              <span>销售价（分）</span>
              <span>库存</span>
              <span>操作</span>
            </div>
          )}
          {skus.map((row, index) => (
            <div key={row.key} className="grid grid-cols-[2fr_1fr_1fr_auto] gap-2 mb-2">
              <Input
                placeholder="规格，如 颜色:红色"
                value={row.specs}
                onChange={(e) => setSkus((list) => list.map((r, i) => (i === index ? { ...r, specs: e.target.value } : r)))}
                style={{ flex: 2 }}
              />
              <InputNumber
                aria-label="销售价（分）"
                placeholder="销售价（分）"
                min={0}
                value={row.price_fen}
                onChange={(v) => setSkus((list) => list.map((r, i) => (i === index ? { ...r, price_fen: v ?? 0 } : r)))}
                style={{ flex: 1 }}
              />
              <InputNumber
                aria-label="库存"
                placeholder="库存"
                min={0}
                value={row.stock}
                onChange={(v) => setSkus((list) => list.map((r, i) => (i === index ? { ...r, stock: v ?? 0 } : r)))}
                style={{ flex: 1 }}
              />
              <Button
                danger
                onClick={() => setSkus((list) => list.filter((_, i) => i !== index))}
              >
                删除
              </Button>
            </div>
          ))}
          <Button
            type="dashed"
            block
            onClick={() =>
              setSkus((list) => [...list, { key: String(Date.now()), specs: '', price_fen: 0, stock: 0 }])
            }
          >
            添加规格
          </Button>
        </Form>
      </Modal>
    </div>
  )
}
