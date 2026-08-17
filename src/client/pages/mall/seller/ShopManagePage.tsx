import { useCallback, useEffect, useState } from 'react'
import { App, Alert, Button, Descriptions, Form, Input, Modal, Space, Spin, Tag } from 'antd'
import { applyMallShop, getMyMallShop, updateMallShop } from '../../../lib/sellerMall'
import FileUpload from '../../../components/files/FileUpload'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { MallShop } from '../../../lib/types'

const STATUS_LABELS: Record<string, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
  closed: { text: '已关闭', color: 'default' },
}

export default function ShopManagePage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [shop, setShop] = useState<MallShop | null>(null)
  const [noShop, setNoShop] = useState(false)
  const [loading, setLoading] = useState(true)
  const [editOpen, setEditOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploadedDocuments, setUploadedDocuments] = useState<Record<string, string>>({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setShop(await getMyMallShop())
      setNoShop(false)
    } catch {
      setShop(null)
      setNoShop(true)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const apply = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      const created = await applyMallShop(values)
      setShop(created)
      setNoShop(false)
      message.success('开店申请已提交，等待管理员审核')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '提交失败'))
    } finally {
      setSaving(false)
    }
  }

  const recordDocumentUpload = (field: string, assetId: string) => {
    form.setFieldValue(field, assetId)
    setUploadedDocuments((current) => ({ ...current, [field]: assetId }))
  }

  const saveEdit = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      setShop(await updateMallShop(values))
      setEditOpen(false)
      message.success('店铺信息已更新')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '保存失败'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    )
  }

  if (noShop) {
    return (
      <div className="rounded bg-white" style={{ padding: '24px 32px', maxWidth: 560 }}>
        <h3 className="text-base font-bold mb-2" style={{ color: '#333' }}>
          申请开店
        </h3>
        <p className="text-xs mb-4" style={{ color: '#999' }}>
          提交身份与经营材料后由平台管理员审核，审核通过后即可发布商品。需缴纳入驻保证金（按平台配置）。
        </p>
        <Form form={form} layout="vertical">
          <Form.Item name="name" label="店铺名称" rules={[{ required: true, message: '请输入店铺名称' }, { max: 50 }]}>
            <Input placeholder="如：示例优选旗舰店" />
          </Form.Item>
          <Form.Item name="description" label="店铺简介" rules={[{ max: 300 }]}>
            <Input.TextArea rows={3} placeholder="介绍一下你的店铺" />
          </Form.Item>
          <Form.Item name="real_name" label="姓名" rules={[{ required: true, message: '请输入姓名' }, { max: 50 }]}>
            <Input placeholder="请输入经营者姓名" />
          </Form.Item>
          <Form.Item name="identity_number" label="身份证号" rules={[{ required: true, message: '请输入身份证号' }, { min: 15, max: 32 }]}>
            <Input placeholder="请输入身份证号码" />
          </Form.Item>
          {[
            ['business_license_asset_id', '营业执照'],
            ['identity_front_asset_id', '身份证正面'],
            ['identity_back_asset_id', '身份证反面'],
          ].map(([field, label]) => (
            <Form.Item key={field} label={label} required>
              <Form.Item name={field} noStyle rules={[{ required: true, message: `请上传${label}` }]}>
                <Input type="hidden" />
              </Form.Item>
              <Space>
                <FileUpload accept="image/*" disabled={saving} onUploaded={(asset) => recordDocumentUpload(field, asset.id)} />
                {uploadedDocuments[field] && <Tag color="green">已上传</Tag>}
              </Space>
            </Form.Item>
          ))}
          <Button type="primary" loading={saving} onClick={apply} style={{ background: '#F31947' }}>
            提交申请
          </Button>
        </Form>
      </div>
    )
  }

  const status = shop ? STATUS_LABELS[shop.status] : null

  return (
    <div className="rounded bg-white space-y-4" style={{ padding: '24px 32px' }}>
      <div className="flex items-center justify-between">
        <h3 className="text-base font-bold" style={{ color: '#333' }}>
          店铺信息
        </h3>
        {status && (
          <Tag color={status.color}>
            {status.text}
            {shop?.status === 'rejected' && shop.reject_reason ? `：${shop.reject_reason}` : ''}
          </Tag>
        )}
      </div>

      {shop?.status === 'pending' && (
        <Alert type="info" showIcon message="店铺正在审核中，审核通过后才能发布商品和接单。" />
      )}
      {shop?.status === 'closed' && (
        <Alert type="warning" showIcon message="店铺已被平台关闭，如有疑问请联系平台。" />
      )}

      <Descriptions column={1} size="middle">
        <Descriptions.Item label="店铺名称">{shop?.name}</Descriptions.Item>
        <Descriptions.Item label="店铺简介">{shop?.description || '-'}</Descriptions.Item>
        <Descriptions.Item label="经营者姓名">{shop?.real_name || '-'}</Descriptions.Item>
        <Descriptions.Item label="身份证号">{shop?.identity_number || '-'}</Descriptions.Item>
        <Descriptions.Item label="入驻保证金">
          ¥{((shop?.deposit_fen ?? 0) / 100).toFixed(2)}
        </Descriptions.Item>
        <Descriptions.Item label="申请时间">{shop?.created_at}</Descriptions.Item>
        <Descriptions.Item label="审核通过时间">{shop?.approved_at || '-'}</Descriptions.Item>
      </Descriptions>

      {shop?.status === 'approved' && (
        <Button onClick={() => setEditOpen(true)}>编辑店铺信息</Button>
      )}

      <Modal
        title="编辑店铺信息"
        open={editOpen}
        onCancel={() => setEditOpen(false)}
        onOk={saveEdit}
        confirmLoading={saving}
        okText="保存"
        cancelText="取消"
      >
        <Form form={form} layout="vertical" className="mt-4" initialValues={shop ?? undefined}>
          <Form.Item name="name" label="店铺名称" rules={[{ required: true, message: '请输入店铺名称' }, { max: 50 }]}>
            <Input />
          </Form.Item>
          <Form.Item name="description" label="店铺简介" rules={[{ max: 300 }]}>
            <Input.TextArea rows={3} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  )
}
