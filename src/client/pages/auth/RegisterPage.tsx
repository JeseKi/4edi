import {
  Alert,
  App,
  Button,
  Card,
  Checkbox,
  Flex,
  Form,
  Input,
  Segmented,
  Space,
  Spin,
  Typography,
} from 'antd'
import {
  LockOutlined,
  MailOutlined,
  MobileOutlined,
  SendOutlined,
  UserAddOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import TurnstileWidget from '../../components/auth/TurnstileWidget'
import { useAuth } from '../../hooks/useAuth'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'
import { resolveApiErrorMessage } from '../../lib/error'
import { listLegalDocuments } from '../../lib/legal'

type RegisterMode = 'email' | 'phone'

const PHONE_PATTERN = /^(?:(?:\+?86)|(?:0086))?1[3-9]\d{9}$/

export default function RegisterPage() {
  const navigate = useNavigate()
  const {
    registerWithCode,
    sendVerificationCode,
    sendPhoneVerificationCode,
    registerWithPhoneCode,
    loading,
    isAuthenticated,
  } = useAuth()
  const { turnstile } = useRuntimeConfig()
  const { message } = App.useApp()
  const turnstileSiteKey = turnstile.siteKey
  const turnstileEnabled = turnstile.enabled

  const [form] = Form.useForm<{
    username?: string
    email?: string
    phone?: string
    password: string
    confirmPassword: string
    code: string
    acceptUserAgreement: boolean
    acceptPrivacyPolicy: boolean
  }>()
  const [mode, setMode] = useState<RegisterMode>('email')
  const [submitting, setSubmitting] = useState(false)
  const [sendingCode, setSendingCode] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [codeCountdown, setCodeCountdown] = useState(0)
  const [turnstileToken, setTurnstileToken] = useState<string | null>(null)
  const [legalVersions, setLegalVersions] = useState<Record<string, string>>({})

  useEffect(() => {
    listLegalDocuments()
      .then((documents) => {
        setLegalVersions(
          Object.fromEntries(documents.map((document) => [document.document_type, document.version])),
        )
      })
      .catch(() => setError('协议加载失败，请刷新页面后重试'))
  }, [])

  useEffect(() => {
    if (!loading && isAuthenticated) {
      navigate('/', { replace: true })
    }
  }, [isAuthenticated, loading, navigate])

  const requireTurnstile = () => {
    if (turnstileEnabled && !turnstileToken) {
      const noTokenError = '请先完成机器人校验'
      setError(noTokenError)
      message.error(noTokenError)
      return true
    }
    return false
  }

  const handleSendCode = async (identifier: string) => {
    if (requireTurnstile()) {
      return
    }
    setSendingCode(true)
    setError(null)
    try {
      if (mode === 'email') {
        await sendVerificationCode({ email: identifier, turnstile_token: turnstileToken ?? undefined })
      } else {
        await sendPhoneVerificationCode({ phone: identifier, turnstile_token: turnstileToken ?? undefined })
      }
      setCodeCountdown(60)
      message.success(mode === 'email' ? '验证码已发送，请查看您的邮箱' : '验证码已发送，请查看您的手机短信')
    } catch (err) {
      const text = resolveApiErrorMessage(err, '验证码发送失败，请稍后再试。')
      setError(text)
      message.error(text)
    } finally {
      setSendingCode(false)
    }
  }

  useEffect(() => {
    if (codeCountdown <= 0) {
      return
    }

    const timer = window.setInterval(() => {
      setCodeCountdown((prev) => (prev <= 1 ? 0 : prev - 1))
    }, 1000)

    return () => window.clearInterval(timer)
  }, [codeCountdown])

  const handleSubmit = async (values: {
    username?: string
    email?: string
    phone?: string
    password: string
    confirmPassword: string
    code: string
    acceptUserAgreement: boolean
    acceptPrivacyPolicy: boolean
  }) => {
    if (requireTurnstile()) {
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const userAgreementVersion = legalVersions.user_agreement
      const privacyPolicyVersion = legalVersions.privacy_policy
      if (!userAgreementVersion || !privacyPolicyVersion) {
        throw new Error('协议版本尚未加载，请稍后重试')
      }
      if (mode === 'email') {
        await registerWithCode({
          username: values.username ?? '',
          email: values.email ?? '',
          password: values.password,
          code: values.code,
          turnstile_token: turnstileToken ?? undefined,
          user_agreement_version: userAgreementVersion,
          privacy_policy_version: privacyPolicyVersion,
        })
      } else {
        await registerWithPhoneCode({
          phone: values.phone ?? '',
          password: values.password,
          code: values.code,
          turnstile_token: turnstileToken ?? undefined,
          user_agreement_version: userAgreementVersion,
          privacy_policy_version: privacyPolicyVersion,
        })
      }
      message.success('注册成功')
      navigate('/login', { state: { registerSuccess: true } })
      form.resetFields()
      setCodeCountdown(0)
    } catch (err) {
      const text = resolveApiErrorMessage(err, '注册失败，请稍后再试。')
      setError(text)
      message.error(text)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <Flex align="center" justify="center" style={{ minHeight: '100vh' }}>
        <Spin tip="正在加载，请稍候" size="large" />
      </Flex>
    )
  }

  return (
    <Flex align="flex-start" justify="center" style={{ minHeight: '100vh', padding: '48px 16px' }}>
      <Card bordered={false} className="theme-card-shadow" style={{ width: '100%', maxWidth: 420 }}>
        <Space direction="vertical" size={24} style={{ width: '100%' }}>
          <div>
            <Typography.Title level={3} style={{ marginBottom: 8 }}>
              创建新账号
            </Typography.Title>
            <Typography.Text type="secondary">
              支持邮箱或手机号注册，注册后即可开启购物之旅。
            </Typography.Text>
          </div>
          <Segmented
            block
            value={mode}
            onChange={(value) => {
              setMode(value as RegisterMode)
              setError(null)
              form.resetFields()
              setCodeCountdown(0)
            }}
            options={[
              { label: '邮箱注册', value: 'email' },
              { label: '手机号注册', value: 'phone' },
            ]}
          />
          {error && <Alert type="error" showIcon message={error} />}
          <Form form={form} layout="vertical" onFinish={handleSubmit} requiredMark={false} autoComplete="on">
            {mode === 'email' ? (
              <>
                <Form.Item
                  label="用户名"
                  name="username"
                  rules={[
                    { required: true, message: '请输入用户名' },
                    { min: 3, message: '用户名至少 3 个字符' },
                  ]}
                >
                  <Input size="large" prefix={<UserOutlined />} placeholder="请输入用户名" autoComplete="username" allowClear />
                </Form.Item>
                <Form.Item
                  label="邮箱"
                  name="email"
                  rules={[
                    { required: true, message: '请输入邮箱地址' },
                    { type: 'email', message: '请输入正确的邮箱格式' },
                  ]}
                >
                  <Input size="large" prefix={<MailOutlined />} placeholder="请输入邮箱地址" autoComplete="email" allowClear />
                </Form.Item>
              </>
            ) : (
              <Form.Item
                label="手机号"
                name="phone"
                rules={[
                  { required: true, message: '请输入手机号' },
                  { pattern: PHONE_PATTERN, message: '请输入正确的手机号格式' },
                ]}
              >
                <Input size="large" prefix={<MobileOutlined />} placeholder="请输入手机号" autoComplete="tel" allowClear />
              </Form.Item>
            )}
            <Form.Item label="验证码">
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <div style={{ flex: 1 }}>
                  <Form.Item
                    name="code"
                    noStyle
                    rules={[
                      { required: true, message: '请输入验证码' },
                      { len: 6, message: '验证码为6位数字' },
                    ]}
                  >
                    <Input size="large" style={{ width: '100%' }} placeholder="请输入验证码" />
                  </Form.Item>
                </div>
                <Button
                  size="large"
                  icon={<SendOutlined />}
                  onClick={async () => {
                    try {
                      const values = await form.validateFields([mode === 'email' ? 'email' : 'phone'])
                      await handleSendCode(mode === 'email' ? (values.email ?? '') : (values.phone ?? ''))
                    } catch {
                      // 表单会自行展示错误信息
                    }
                  }}
                  loading={sendingCode}
                  disabled={sendingCode || codeCountdown > 0}
                  style={{ width: 112, flex: '0 0 112px' }}
                >
                  {codeCountdown > 0 ? `${codeCountdown}s` : '发送'}
                </Button>
              </div>
            </Form.Item>
            <Form.Item
              label="密码"
              name="password"
              rules={[
                { required: true, message: '请输入密码' },
                { min: 8, message: '密码至少 8 个字符' },
              ]}
            >
              <Input.Password size="large" prefix={<LockOutlined />} placeholder="请输入密码" autoComplete="new-password" />
            </Form.Item>
            <Form.Item
              label="确认密码"
              name="confirmPassword"
              dependencies={['password']}
              rules={[
                { required: true, message: '请再次输入密码' },
                ({ getFieldValue }) => ({
                  validator(_, value) {
                    if (!value || getFieldValue('password') === value) {
                      return Promise.resolve()
                    }
                    return Promise.reject(new Error('两次输入的密码不一致'))
                  },
                }),
              ]}
            >
              <Input.Password size="large" prefix={<LockOutlined />} placeholder="请再次输入密码" autoComplete="new-password" />
            </Form.Item>
            <Form.Item
              name="acceptUserAgreement"
              valuePropName="checked"
              rules={[{ validator: (_, value) => value ? Promise.resolve() : Promise.reject(new Error('请阅读并同意用户服务协议')) }]}
            >
              <Checkbox>
                我已阅读并同意{' '}
                <a href="/legal/user-agreement" target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
                  《用户服务协议》
                </a>
              </Checkbox>
            </Form.Item>
            <Form.Item
              name="acceptPrivacyPolicy"
              valuePropName="checked"
              rules={[{ validator: (_, value) => value ? Promise.resolve() : Promise.reject(new Error('请阅读并同意隐私政策')) }]}
            >
              <Checkbox>
                我已阅读并同意{' '}
                <a href="/legal/privacy-policy" target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
                  《隐私政策》
                </a>
              </Checkbox>
            </Form.Item>
            {turnstileEnabled ? (
              <Form.Item>
                <TurnstileWidget
                  siteKey={turnstileSiteKey}
                  scriptUrl={turnstile.scriptUrl}
                  action="auth_register_with_code"
                  onToken={setTurnstileToken}
                />
              </Form.Item>
            ) : null}
            <Form.Item>
              <Button
                type="primary"
                htmlType="submit"
                size="large"
                icon={<UserAddOutlined />}
                loading={submitting}
                disabled={!legalVersions.user_agreement || !legalVersions.privacy_policy}
                block
              >
                注册
              </Button>
            </Form.Item>
          </Form>
          <Flex justify="center" gap={8}>
            <Typography.Text type="secondary">已有账号？</Typography.Text>
            <Link to="/login" className="theme-link">
              返回登录
            </Link>
          </Flex>
        </Space>
      </Card>
    </Flex>
  )
}
