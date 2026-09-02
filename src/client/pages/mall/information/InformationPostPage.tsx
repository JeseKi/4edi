import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { App, Button, Col, Form, Input, Row, Select, Spin } from 'antd'
import { SendOutlined, ArrowRightOutlined } from '@ant-design/icons'
import { createInformation, listInformationCategories, listMyPublisherVerifications } from '../../../lib/information'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { InfoCategory } from '../../../lib/types'
import { Alert } from 'antd'
import { Link } from 'react-router-dom'
import CurrentLegalConsent from '../../../components/legal/CurrentLegalConsent'

const MALL_PRIMARY = '#F31947'

const STEPS = [
  '登录账号，进入「发布信息」',
  '选择分类，填写标题、价格与联系方式',
  '按所选分类补充属性字段',
  '提交后等待平台审核',
  '审核通过后将在信息中心公开展示',
]

export default function InformationPostPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [categories, setCategories] = useState<InfoCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [verificationValid, setVerificationValid] = useState(false)
  const categoryKey = Form.useWatch('category', form)

  useEffect(() => {
    listInformationCategories()
      .then(setCategories)
      .catch((err) => message.error(resolveApiErrorMessage(err, '分类加载失败')))
      .finally(() => setLoading(false))
  }, [message])

  useEffect(() => {
    listMyPublisherVerifications()
      .then((items) => setVerificationValid(items.some((item) => item.is_currently_valid)))
      .catch(() => setVerificationValid(false))
  }, [])

  const currentCategory = useMemo(
    () => categories.find((c) => c.key === categoryKey) ?? null,
    [categories, categoryKey],
  )

  const renderAttributeField = useCallback(
    (attr: { key: string; label: string; type: string; options?: string[] }) => {
      if (attr.type === 'select' && attr.options?.length) {
        return (
          <Select
            placeholder={`请选择${attr.label}`}
            allowClear
            options={attr.options.map((o) => ({ label: o, value: o }))}
          />
        )
      }
      if (attr.type === 'textarea') {
        return <Input.TextArea rows={3} placeholder={`请输入${attr.label}`} maxLength={200} showCount />
      }
      return <Input placeholder={`请输入${attr.label}`} maxLength={100} />
    },
    [],
  )

  const submit = async () => {
    const values = await form.validateFields()
    const attributes: Record<string, string> = {}
    if (currentCategory) {
      currentCategory.attributes.forEach((attr) => {
        const value = values[attr.key]
        if (value) attributes[attr.key] = String(value)
      })
    }
    setSubmitting(true)
    try {
      await createInformation({
        category: values.category,
        title: values.title,
        price: values.price,
        contact_name: values.contact_name,
        contact_phone: values.contact_phone,
        content: values.content,
        attributes: Object.keys(attributes).length ? attributes : undefined,
      })
      message.success('发布成功，等待平台审核')
      navigate('/mall/information/mine')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '发布失败'))
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    )
  }

  return (
    <div className="flex gap-4 items-start">
      <div className="flex-1 min-w-0 rounded-lg bg-white p-6">
        <CurrentLegalConsent />
        {!verificationValid && (
          <Alert
            className="mb-4"
            type="warning"
            showIcon
            message="发布信息前需要完成发布者实名核验"
            description={<Link to="/mall/information/verification">查看实名状态或提交核验材料</Link>}
          />
        )}
        <h3 className="text-base font-bold mb-4" style={{ color: '#333' }}>
          发布信息
        </h3>
        <Form form={form} layout="vertical" initialValues={{ category: categories[0]?.key }}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="category"
                label="信息分类"
                rules={[{ required: true, message: '请选择信息分类' }]}
              >
                <Select
                  placeholder="请选择分类"
                  options={categories.map((c) => ({ label: c.name, value: c.key }))}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="title"
                label="信息标题"
                rules={[
                  { required: true, message: '请输入信息标题' },
                  { max: 120, message: '标题不超过 120 字' },
                ]}
              >
                <Input placeholder="一句话概括你所提供的信息/服务" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="price" label="价格（可填 面议 / 电话咨询 / 具体金额）" rules={[{ max: 50 }]}>
                <Input placeholder="如：面议 / 8000元起" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="contact_name"
                label="联系人"
                rules={[{ required: true, message: '请输入联系人' }, { max: 50 }]}
              >
                <Input placeholder="请输入联系人姓名/昵称" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="contact_phone" label="联系电话（游客浏览时将打码）" rules={[{ max: 32 }]}>
                <Input placeholder="请输入联系电话" />
              </Form.Item>
            </Col>
          </Row>

          {currentCategory && (
            <Row gutter={16}>
              {currentCategory.attributes.map((attr) => (
                <Col span={12} key={attr.key}>
                  <Form.Item name={attr.key} label={attr.label}>
                    {renderAttributeField(attr)}
                  </Form.Item>
                </Col>
              ))}
            </Row>
          )}

          <Form.Item
            name="content"
            label="详情内容"
            rules={[
              { required: true, message: '请输入详情内容' },
              { max: 5000, message: '详情内容不超过 5000 字' },
            ]}
          >
            <Input.TextArea rows={6} placeholder="详细介绍你的信息/服务：功能、优势、交付等" maxLength={5000} showCount />
          </Form.Item>

          <Button
            type="primary"
            size="large"
            icon={<SendOutlined />}
            loading={submitting}
            disabled={!verificationValid}
            onClick={submit}
            style={{ background: MALL_PRIMARY }}
          >
            提交发布
          </Button>
        </Form>
      </div>

      {/* 信息发布快速上手 */}
      <div className="hidden lg:block w-64 shrink-0 rounded-lg bg-white p-4">
        <div className="text-sm font-bold mb-3" style={{ color: MALL_PRIMARY }}>
          信息发布快速上手
        </div>
        <div className="space-y-3">
          {STEPS.map((step, index) => (
            <div key={step} className="flex items-start gap-2 text-sm" style={{ color: '#555' }}>
              <span
                className="inline-flex items-center justify-center rounded-full text-xs shrink-0 mt-0.5"
                style={{ width: 18, height: 18, background: '#fff1f0', color: MALL_PRIMARY }}
              >
                {index + 1}
              </span>
              <span>{step}</span>
            </div>
          ))}
        </div>
        <div className="mt-4 text-xs flex items-center" style={{ color: '#bbb' }}>
          <ArrowRightOutlined style={{ marginRight: 4 }} />
          发布后请在「我的发布」查看审核进度
        </div>
      </div>
    </div>
  )
}
