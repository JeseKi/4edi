import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { App, Button, Form, Input } from 'antd'
import { createComplaint } from '../../lib/complaint'
import { resolveApiErrorMessage } from '../../lib/error'

const MALL_PRIMARY = '#F31947'

export default function ComplaintPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [form] = Form.useForm()
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await createComplaint({
        subject: values.subject,
        content: values.content,
        contact: values.contact,
      })
      message.success('投诉已提交，我们会尽快处理')
      navigate('/mall/information')
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '提交失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex gap-4 items-start">
      <div className="flex-1 min-w-0 rounded-lg bg-white p-6">
        <h3 className="text-base font-bold mb-1" style={{ color: '#333' }}>
          投诉入口
        </h3>
        <p className="text-sm mb-4" style={{ color: '#888' }}>
          发现不良信息或违规内容，可在此提交投诉，我们会尽快核实处理。
        </p>
        <Form form={form} layout="vertical">
          <Form.Item
            name="subject"
            label="投诉对象"
            rules={[
              { required: true, message: '请输入投诉对象' },
              { max: 120, message: '不超过 120 字' },
            ]}
          >
            <Input placeholder="如：某条信息的标题 / 发布者 / 链接" maxLength={120} />
          </Form.Item>

          <Form.Item
            name="content"
            label="投诉说明"
            rules={[
              { required: true, message: '请输入投诉说明' },
              { max: 2000, message: '不超过 2000 字' },
            ]}
          >
            <Input.TextArea
              rows={6}
              placeholder="请描述具体违规情况，便于我们核实"
              maxLength={2000}
              showCount
            />
          </Form.Item>

          <Form.Item name="contact" label="联系方式（选填，便于我们回复）" rules={[{ max: 120 }]}>
            <Input placeholder="如：手机号 / 邮箱 / 微信" maxLength={120} />
          </Form.Item>

          <Button
            type="primary"
            size="large"
            loading={submitting}
            onClick={submit}
            style={{ background: MALL_PRIMARY }}
          >
            提交投诉
          </Button>
        </Form>
      </div>
    </div>
  )
}
