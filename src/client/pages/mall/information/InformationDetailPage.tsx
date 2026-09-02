import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { Breadcrumb, Button, Descriptions, Spin, Tag, Typography } from 'antd'
import { ArrowLeftOutlined, EyeOutlined, PhoneOutlined, UserOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { getInformationContact, getInformationDetail, listInformationCategories } from '../../../lib/information'
import { resolveApiErrorMessage } from '../../../lib/error'
import { App } from 'antd'
import type { InfoCategory, InformationPostDetail } from '../../../lib/types'
import { useAuth } from '../../../hooks/useAuth'

const MALL_PRIMARY = '#F31947'

const DISCLAIMER =
  '本页面所展现的信息由发布者提供，平台仅作展示。信息的真实性、准确性和合法性由发布者负责，请谨慎辨别，谨防欺诈。'

export default function InformationDetailPage() {
  const { postId } = useParams()
  const { message } = App.useApp()
  const { isAuthenticated } = useAuth()
  const [detail, setDetail] = useState<InformationPostDetail | null>(null)
  const [labels, setLabels] = useState<Record<string, string>>({})
  const [notFound, setNotFound] = useState(false)
  const [loading, setLoading] = useState(true)
  const [contactPhone, setContactPhone] = useState<string | null>(null)
  const [contactLoading, setContactLoading] = useState(false)

  const revealContact = async () => {
    setContactLoading(true)
    try {
      const contact = await getInformationContact(Number(postId))
      setContactPhone(contact.contact_phone)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '联系方式加载失败'))
    } finally {
      setContactLoading(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    listInformationCategories()
      .then((cats: InfoCategory[]) => {
        if (!cancelled) {
          const map: Record<string, string> = {}
          cats.forEach((c) => c.attributes.forEach((a) => (map[a.key] = a.label)))
          setLabels(map)
        }
      })
      .catch(() => {
        // 属性标签缺失不阻塞详情展示
      })
    setLoading(true)
    getInformationDetail(Number(postId))
      .then((data) => {
        if (!cancelled) setDetail(data)
      })
      .catch((err) => {
        if (!cancelled) {
          setNotFound(true)
          message.error(resolveApiErrorMessage(err, '信息加载失败'))
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [postId, message])

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <Spin size="large" />
      </div>
    )
  }

  if (notFound || !detail) {
    return (
      <div className="rounded-lg bg-white py-24 text-center">
        <div className="mb-3" style={{ color: '#999' }}>
          信息不存在或未通过审核
        </div>
        <Link to="/mall/information">
          <Button type="primary" style={{ background: MALL_PRIMARY }}>
            返回信息中心
          </Button>
        </Link>
      </div>
    )
  }

  const attributes = detail.attributes ?? {}

  return (
    <div className="space-y-4">
      <Breadcrumb
        items={[
          { title: <Link to="/mall/information">分类信息</Link> },
          { title: detail.category_name },
          { title: detail.title },
        ]}
      />

      <div className="rounded-lg bg-white p-6">
        <div className="flex items-center gap-2 mb-2">
          {detail.is_top && <Tag color="volcano">置顶</Tag>}
          <Typography.Title level={3} style={{ margin: 0, color: '#222' }}>
            {detail.title}
          </Typography.Title>
        </div>
        <div className="flex flex-wrap items-center gap-5 text-xs mb-4" style={{ color: '#999' }}>
          <span>
            <UserOutlined style={{ marginRight: 4 }} />
            信息发布人：{detail.poster_username}
          </span>
          <span>发布时间：{dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</span>
          <span>
            <EyeOutlined style={{ marginRight: 4 }} />
            {detail.view_count} 次浏览
          </span>
        </div>

        <div className="flex flex-col md:flex-row gap-6">
          <div className="flex-1 min-w-0">
            {/* 联系方式 */}
            <div
              className="rounded px-4 py-3 mb-4"
              style={{ background: '#fff7e6', border: '1px solid #ffe7ba' }}
            >
              <div className="flex flex-wrap gap-x-8 gap-y-1 text-sm">
                <span style={{ color: '#d46b08' }}>
                  价格：<b>{detail.price || '面议'}</b>
                </span>
                <span style={{ color: '#333' }}>联系人：{detail.contact_name}</span>
                <span style={{ color: '#333' }}>
                  <PhoneOutlined style={{ marginRight: 4 }} />
                  电话：<b>{contactPhone || detail.contact_phone || '-'}</b>
                </span>
                {contactPhone ? (
                  <a href={`tel:${contactPhone}`}>拨打电话</a>
                ) : isAuthenticated ? (
                  <Button size="small" type="primary" loading={contactLoading} onClick={() => void revealContact()}>
                    查看完整电话
                  </Button>
                ) : (
                  <Link to="/login">登录后查看完整电话</Link>
                )}
              </div>
              {contactPhone && <div className="mt-2 text-xs" style={{ color: '#ad6800' }}>完整号码仅用于联系本条信息发布者，请勿用于其他用途。</div>}
            </div>

            {/* 详情 */}
            <div className="mb-4">
              <div className="text-base font-bold mb-2" style={{ color: '#333' }}>
                详情
              </div>
              <Typography.Paragraph
                style={{ whiteSpace: 'pre-wrap', color: '#444', marginBottom: 0 }}
              >
                {detail.content}
              </Typography.Paragraph>
            </div>

            {/* 分类属性 */}
            {Object.keys(attributes).length > 0 && (
              <div className="mb-4">
                <div className="text-base font-bold mb-2" style={{ color: '#333' }}>
                  {detail.category_name}属性
                </div>
                <Descriptions
                  bordered
                  size="small"
                  column={{ xs: 1, sm: 2, md: 2 }}
                  items={Object.entries(attributes).map(([key, value]) => ({
                    key,
                    label: labels[key] ?? key,
                    children: value,
                  }))}
                />
              </div>
            )}

            <div
              className="rounded px-4 py-3 text-xs"
              style={{ background: '#fafafa', color: '#999' }}
            >
              <div className="font-bold mb-1">免责声明</div>
              {DISCLAIMER}
            </div>
          </div>
        </div>

        <div className="mt-6">
          <Link to="/mall/information">
            <Button icon={<ArrowLeftOutlined />}>返回信息中心</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}
