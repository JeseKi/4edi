import { useCallback, useEffect, useState } from 'react'
import { App, Button, Descriptions, Form, Image, Input, Modal, Popconfirm, Table, Tabs, Tag } from 'antd'
import { closeAdminShop, listAdminShops, reopenAdminShop, reviewAdminShop } from '../../../lib/sellerMall'
import api from '../../../lib/api'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { MallShop, MallShopStatus } from '../../../lib/types'

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
  closed: { text: '已关闭', color: 'default' },
}

const TABS = [
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已驳回' },
  { key: 'closed', label: '已关闭' },
  { key: '', label: '全部' },
]

export default function ShopReviewPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [status, setStatus] = useState<MallShopStatus | ''>('pending')
  const [page, setPage] = useState(1)
  const [shops, setShops] = useState<MallShop[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [reviewTarget, setReviewTarget] = useState<MallShop | null>(null)
  const [reviewApproved, setReviewApproved] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [documentPreview, setDocumentPreview] = useState<{ title: string; url: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listAdminShops({ status: status || undefined, page, page_size: 10 })
      setShops(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '店铺列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [status, page, message])

  useEffect(() => {
    setPage(1)
  }, [status])

  useEffect(() => {
    load()
  }, [load])

  const submitReview = async () => {
    if (!reviewTarget) return
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await reviewAdminShop(reviewTarget.id, {
        approved: reviewApproved,
        reject_reason: reviewApproved ? undefined : values.reject_reason,
      })
      message.success(reviewApproved ? '店铺已通过审核' : '店铺已驳回')
      setReviewTarget(null)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const closeShop = async (shop: MallShop) => {
    try {
      await closeAdminShop(shop.id)
      message.success('店铺已关闭，其商品已全部下架')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '关闭失败'))
    }
  }

  const reopenShop = async (shop: MallShop) => {
    try {
      await reopenAdminShop(shop.id)
      message.success('店铺已开启；商品仍保持下架，需商家自行上架')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '开启失败'))
    }
  }

  const previewDocument = async (title: string, assetId: string | null) => {
    if (!assetId) return
    try {
      const { data } = await api.get<Blob>(`/files/${assetId}/download`, { responseType: 'blob' })
      setDocumentPreview({ title, url: URL.createObjectURL(data) })
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '材料加载失败'))
    }
  }

  const closeDocumentPreview = () => {
    if (documentPreview) URL.revokeObjectURL(documentPreview.url)
    setDocumentPreview(null)
  }

  const columns = [
    { title: '店铺名称', dataIndex: 'name', key: 'name' },
    { title: '店主 ID', dataIndex: 'owner_user_id', key: 'owner_user_id' },
    { title: '简介', dataIndex: 'description', key: 'description', ellipsis: true },
    {
      title: '保证金',
      dataIndex: 'deposit_fen',
      key: 'deposit_fen',
      render: (fen: number) => `¥${(fen / 100).toFixed(2)}`,
    },
    { title: '申请时间', dataIndex: 'created_at', key: 'created_at' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: MallShop['status']) => {
        const label = STATUS_LABELS[s]
        return <Tag color={label?.color}>{label?.text ?? s}</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: MallShop) => (
        <div className="flex gap-1">
          {record.status === 'pending' && (
            <>
              <Button size="small" type="primary" onClick={() => { setReviewApproved(true); setReviewTarget(record) }}>
                通过
              </Button>
              <Button size="small" danger onClick={() => { setReviewApproved(false); setReviewTarget(record) }}>
                驳回
              </Button>
            </>
          )}
          {record.status === 'approved' && (
            <Popconfirm title="关闭店铺后其商品将全部下架，确定？" onConfirm={() => closeShop(record)}>
              <Button size="small" danger>
                关闭店铺
              </Button>
            </Popconfirm>
          )}
          {record.status === 'closed' && (
            <Popconfirm title="开启店铺后，商品仍保持下架，确定？" onConfirm={() => reopenShop(record)}>
              <Button size="small" type="primary">
                开启店铺
              </Button>
            </Popconfirm>
          )}
          {record.status === 'rejected' && (
            <span className="text-xs" style={{ color: '#999' }}>
              {record.reject_reason || '-'}
            </span>
          )}
        </div>
      ),
    },
  ]

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        店铺审核
      </h3>
      <Tabs
        activeKey={status}
        items={TABS}
        onChange={(key) => setStatus(key as MallShopStatus | '')}
        className="mb-2"
      />

      <Table
        rowKey="id"
        columns={columns}
        dataSource={shops}
        loading={loading}
        expandable={{
          expandedRowRender: (record: MallShop) => (
            <Descriptions size="small" column={1}>
              <Descriptions.Item label="经营者姓名">{record.real_name || '-'}</Descriptions.Item>
              <Descriptions.Item label="身份证号">{record.identity_number || '-'}</Descriptions.Item>
              <Descriptions.Item label="审核材料">
                <div className="flex flex-wrap gap-2">
                  <Button size="small" disabled={!record.business_license_asset_id} onClick={() => void previewDocument('营业执照', record.business_license_asset_id)}>
                    营业执照
                  </Button>
                  <Button size="small" disabled={!record.identity_front_asset_id} onClick={() => void previewDocument('身份证正面', record.identity_front_asset_id)}>
                    身份证正面
                  </Button>
                  <Button size="small" disabled={!record.identity_back_asset_id} onClick={() => void previewDocument('身份证反面', record.identity_back_asset_id)}>
                    身份证反面
                  </Button>
                </div>
              </Descriptions.Item>
              <Descriptions.Item label="驳回原因">{record.reject_reason || '-'}</Descriptions.Item>
              <Descriptions.Item label="审核通过时间">{record.approved_at || '-'}</Descriptions.Item>
            </Descriptions>
          ),
        }}
        pagination={{ current: page, pageSize: 10, total, onChange: setPage, showSizeChanger: false }}
      />

      <Modal
        title={reviewApproved ? '通过店铺审核' : '驳回店铺申请'}
        open={reviewTarget != null}
        onCancel={() => setReviewTarget(null)}
        onOk={submitReview}
        confirmLoading={submitting}
        okText="确认"
        cancelText="取消"
      >
        {reviewApproved ? (
          <p className="text-sm" style={{ color: '#666' }}>
            通过后「{reviewTarget?.name}」即可发布商品并接单，并将按平台配置扣入驻保证金。
          </p>
        ) : (
          <Form form={form} layout="vertical" className="mt-4">
            <Form.Item name="reject_reason" label="驳回原因" rules={[{ required: true, message: '请填写驳回原因' }, { max: 200 }]}>
              <Input.TextArea rows={3} placeholder="如：营业执照信息不完整" />
            </Form.Item>
          </Form>
        )}
      </Modal>

      <Modal title={documentPreview?.title} open={documentPreview != null} footer={null} onCancel={closeDocumentPreview} width={720}>
        {documentPreview && <Image src={documentPreview.url} alt={documentPreview.title} style={{ width: '100%' }} />}
      </Modal>
    </div>
  )
}
