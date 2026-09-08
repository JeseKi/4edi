import { useState } from 'react'
import { Alert, Button, Checkbox, DatePicker, Form, Input, Space, Tag } from 'antd'
import dayjs from 'dayjs'
import FileUpload from '../../../components/files/FileUpload'
import type { MallShopApplicationPayload } from '../../../lib/sellerMall'

export default function ShopQualificationForm({
  saving,
  submitLabel,
  initialValues,
  onSubmit,
}: {
  saving: boolean
  submitLabel: string
  initialValues?: Record<string, unknown>
  onSubmit: (payload: MallShopApplicationPayload) => Promise<void>
}) {
  const [form] = Form.useForm()
  const [uploads, setUploads] = useState<Record<string, string>>({})
  const longTerm = Form.useWatch('business_license_long_term', form)

  const recordUpload = (field: string, assetId: string) => {
    form.setFieldValue(field, assetId)
    setUploads((current) => ({ ...current, [field]: assetId }))
  }

  const submit = async () => {
    const values = await form.validateFields()
    await onSubmit({
      ...values,
      business_license_valid_until: values.business_license_valid_until?.format('YYYY-MM-DD'),
      business_license_long_term: Boolean(values.business_license_long_term),
      special_license_not_required: true,
    })
  }

  return (
    <Form form={form} layout="vertical" initialValues={{ ...initialValues, business_license_long_term: false, special_license_not_required: false }}>
      <Alert
        className="mb-4"
        type="warning"
        showIcon
        message="首期暂不支持需要专项许可的行业"
        description="平台首期开放一般商品和技术服务类目；暂不接受依法需取得专项行政许可、备案或专业资质后方可经营的主体、商品或服务。"
      />
      <Form.Item name="name" label="店铺名称" rules={[{ required: true, message: '请输入店铺名称' }, { min: 2, max: 100 }]}><Input /></Form.Item>
      <Form.Item name="description" label="店铺简介" rules={[{ max: 500 }]}><Input.TextArea rows={2} /></Form.Item>
      <Form.Item name="legal_entity_name" label="企业法定全称" rules={[{ required: true, message: '请输入营业执照上的企业全称' }, { max: 200 }]}><Input /></Form.Item>
      <Form.Item name="unified_social_credit_code" label="统一社会信用代码" rules={[{ required: true, message: '请输入统一社会信用代码' }, { pattern: /^[0-9A-Z]{18}$/, message: '请输入 18 位大写统一社会信用代码' }]}><Input maxLength={18} /></Form.Item>
      <Form.Item name="legal_representative" label="法定代表人" rules={[{ required: true }, { max: 100 }]}><Input /></Form.Item>
      <Form.Item name="registered_address" label="注册地址" rules={[{ required: true }, { min: 5, max: 500 }]}><Input /></Form.Item>
      <Form.Item name="business_address" label="实际经营地址" rules={[{ required: true }, { min: 5, max: 500 }]}><Input /></Form.Item>
      <Form.Item name="contact_phone" label="企业联系电话" rules={[{ required: true }, { min: 5, max: 32 }]}><Input /></Form.Item>
      <Form.Item name="real_name" label="经办人真实姓名" rules={[{ required: true }, { max: 50 }]}><Input /></Form.Item>
      <Form.Item name="identity_number" label="经办人证件号码" rules={[{ required: true }, { min: 15, max: 32 }]}><Input /></Form.Item>
      <Form.Item name="business_license_long_term" valuePropName="checked"><Checkbox>营业执照长期有效</Checkbox></Form.Item>
      {!longTerm && <Form.Item name="business_license_valid_until" label="营业执照有效期至" rules={[{ required: true, message: '请选择有效期或勾选长期有效' }]}><DatePicker disabledDate={(value) => value.isBefore(dayjs(), 'day')} /></Form.Item>}
      {[
        ['business_license_asset_id', '营业执照', 'image/*,application/pdf'],
        ['identity_front_asset_id', '经办人证件正面', 'image/*,application/pdf'],
        ['identity_back_asset_id', '经办人证件反面', 'image/*,application/pdf'],
      ].map(([field, label, accept]) => (
        <Form.Item key={field} label={label} required>
          <Form.Item name={field} noStyle rules={[{ required: true, message: `请上传${label}` }]}><Input type="hidden" /></Form.Item>
          <Space><FileUpload accept={accept} disabled={saving} onUploaded={(asset) => recordUpload(field, asset.id)} />{uploads[field] && <Tag color="green">已上传</Tag>}</Space>
        </Form.Item>
      ))}
      <Form.Item
        name="special_license_not_required"
        valuePropName="checked"
        rules={[{
          validator: (_, value) => value
            ? Promise.resolve()
            : Promise.reject(new Error('请确认拟经营内容不涉及专项许可行业')),
        }]}
      >
        <Checkbox>
          我确认拟经营的商品或服务不属于需要专项行政许可、备案或专业资质的行业
        </Checkbox>
      </Form.Item>
      <Button type="primary" loading={saving} onClick={() => void submit()}>{submitLabel}</Button>
    </Form>
  )
}
