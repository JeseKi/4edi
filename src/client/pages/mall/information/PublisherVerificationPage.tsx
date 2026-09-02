import { useCallback, useEffect, useState } from 'react'
import {
  Alert,
  App,
  Button,
  Checkbox,
  DatePicker,
  Descriptions,
  Form,
  Input,
  Select,
  Space,
  Spin,
  Tag,
} from 'antd'
import dayjs from 'dayjs'
import FileUpload from '../../../components/files/FileUpload'
import CurrentLegalConsent from '../../../components/legal/CurrentLegalConsent'
import {
  listMyPublisherVerifications,
  submitPublisherVerification,
} from '../../../lib/information'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { PublisherVerification } from '../../../lib/types'

const STATUS: Record<string, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
}

export default function PublisherVerificationPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [items, setItems] = useState<PublisherVerification[]>([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [uploads, setUploads] = useState<Record<string, string>>({})
  const longTerm = Form.useWatch('document_long_term', form)

  const load = useCallback(() => {
    setLoading(true)
    listMyPublisherVerifications()
      .then(setItems)
      .catch((err) => message.error(resolveApiErrorMessage(err, '实名记录加载失败')))
      .finally(() => setLoading(false))
  }, [message])

  useEffect(load, [load])
  const hasPending = items.some((item) => item.status === 'pending')
  const hasValid = items.some((item) => item.is_currently_valid)

  const upload = (field: string, assetId: string) => {
    form.setFieldValue(field, assetId)
    setUploads((current) => ({ ...current, [field]: assetId }))
  }

  const submit = async () => {
    const values = await form.validateFields()
    setSaving(true)
    try {
      await submitPublisherVerification({
        real_name: values.real_name,
        document_type: values.document_type,
        document_number: values.document_number,
        document_front_asset_id: values.document_front_asset_id,
        document_back_asset_id: values.document_back_asset_id,
        document_valid_until: values.document_valid_until?.format('YYYY-MM-DD'),
        document_long_term: Boolean(values.document_long_term),
      })
      message.success('实名申请已提交，请等待平台审核')
      form.resetFields()
      setUploads({})
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '实名申请提交失败'))
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div className="flex justify-center py-24"><Spin size="large" /></div>

  return (
    <div className="space-y-4">
      <CurrentLegalConsent />
      {hasValid && <Alert type="success" showIcon message="当前实名核验有效，可以发布信息。" />}
      {hasPending && <Alert type="info" showIcon message="实名材料正在审核中，审核完成前暂不能发布信息。" />}

      {!hasValid && !hasPending && (
        <div className="rounded-lg bg-white p-6">
          <h3 className="text-base font-bold mb-4">提交发布者实名核验</h3>
          <Form form={form} layout="vertical" initialValues={{ document_type: 'resident_identity_card', document_long_term: false }}>
            <Form.Item name="real_name" label="真实姓名" rules={[{ required: true, message: '请输入真实姓名' }]}>
              <Input maxLength={100} />
            </Form.Item>
            <Form.Item name="document_type" label="证件类型" rules={[{ required: true }]}>
              <Select options={[{ label: '居民身份证', value: 'resident_identity_card' }, { label: '护照', value: 'passport' }]} />
            </Form.Item>
            <Form.Item name="document_number" label="证件号码" rules={[{ required: true, message: '请输入证件号码' }, { min: 5, max: 64 }]}>
              <Input />
            </Form.Item>
            {[
              ['document_front_asset_id', '证件人像面/首页'],
              ['document_back_asset_id', '证件国徽面/背面'],
            ].map(([field, label]) => (
              <Form.Item key={field} label={label} required={field === 'document_front_asset_id'}>
                <Form.Item name={field} noStyle rules={field === 'document_front_asset_id' ? [{ required: true, message: `请上传${label}` }] : []}>
                  <Input type="hidden" />
                </Form.Item>
                <Space><FileUpload accept="image/*,application/pdf" disabled={saving} onUploaded={(asset) => upload(field, asset.id)} />{uploads[field] && <Tag color="green">已上传</Tag>}</Space>
              </Form.Item>
            ))}
            <Form.Item name="document_long_term" valuePropName="checked"><Checkbox>证件长期有效</Checkbox></Form.Item>
            {!longTerm && (
              <Form.Item name="document_valid_until" label="证件有效期至" rules={[{ required: true, message: '请选择证件有效期' }]}>
                <DatePicker disabledDate={(value) => value.isBefore(dayjs(), 'day')} />
              </Form.Item>
            )}
            <Button type="primary" loading={saving} onClick={() => void submit()}>提交审核</Button>
          </Form>
        </div>
      )}

      <div className="rounded-lg bg-white p-6">
        <h3 className="text-base font-bold mb-4">实名核验历史</h3>
        {items.length === 0 ? <span style={{ color: '#999' }}>暂无记录</span> : items.map((item) => (
          <Descriptions key={item.id} bordered size="small" column={1} className="mb-4">
            <Descriptions.Item label="申请编号">{item.id}</Descriptions.Item>
            <Descriptions.Item label="姓名">{item.real_name}</Descriptions.Item>
            <Descriptions.Item label="证件号码">{item.document_number_masked}</Descriptions.Item>
            <Descriptions.Item label="提交时间">{dayjs(item.submitted_at).format('YYYY-MM-DD HH:mm')}</Descriptions.Item>
            <Descriptions.Item label="状态"><Tag color={STATUS[item.status].color}>{STATUS[item.status].text}</Tag></Descriptions.Item>
            <Descriptions.Item label="驳回原因">{item.reject_reason || '-'}</Descriptions.Item>
          </Descriptions>
        ))}
      </div>
    </div>
  )
}
