import { useCallback, useEffect, useState } from 'react'
import {
  App,
  Button,
  Descriptions,
  Drawer,
  Form,
  Input,
  Modal,
  Popconfirm,
  Table,
  Tabs,
  Tag,
} from 'antd'
import { Link } from 'react-router-dom'
import dayjs from 'dayjs'
import {
  adminListInformation,
  adminReviewInformation,
  adminToggleInformationTop,
} from '../../../lib/information'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { InfoStatus, InformationAdminPost } from '../../../lib/types'

const MALL_PRIMARY = '#F31947'

const STATUS_LABELS: Record<InfoStatus, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
}

const TABS = [
  { key: 'pending', label: '待审核' },
  { key: 'approved', label: '已通过' },
  { key: 'rejected', label: '已驳回' },
  { key: '', label: '全部' },
]

export default function InformationAdminPage() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [status, setStatus] = useState<InfoStatus | ''>('pending')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState<InformationAdminPost[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<InformationAdminPost | null>(null)
  const [reviewTarget, setReviewTarget] = useState<InformationAdminPost | null>(null)
  const [reviewApproved, setReviewApproved] = useState(true)
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await adminListInformation({
        status: status || undefined,
        keyword: keyword || undefined,
        page,
        page_size: 10,
      })
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '信息列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [status, keyword, page, message])

  useEffect(() => {
    setPage(1)
  }, [status, keyword])

  useEffect(() => {
    load()
  }, [load])

  const submitReview = async () => {
    if (!reviewTarget) return
    const values = await form.validateFields()
    setSubmitting(true)
    try {
      await adminReviewInformation(reviewTarget.id, {
        approved: reviewApproved,
        reject_reason: reviewApproved ? undefined : values.reject_reason,
      })
      message.success(reviewApproved ? '信息已通过审核' : '信息已驳回')
      setReviewTarget(null)
      form.resetFields()
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const toggleTop = async (record: InformationAdminPost, on: boolean) => {
    try {
      await adminToggleInformationTop(record.id, on)
      message.success(on ? '已设为置顶' : '已取消置顶')
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '操作失败'))
    }
  }

  const labels: Record<InfoStatus, { text: string; color: string }> = STATUS_LABELS

  const columns = [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      render: (_: string, record: InformationAdminPost) =>
        record.status === 'approved' ? (
          <Link to={`/mall/information/${record.id}`}>{record.title}</Link>
        ) : (
          <span>{record.title}</span>
        ),
    },
    { title: '分类', dataIndex: 'category_name', key: 'category_name' },
    { title: '发布人', dataIndex: 'poster_username', key: 'poster_username' },
    { title: '联系电话', dataIndex: 'contact_phone', key: 'contact_phone', render: (v: string | null) => v || '-' },
    {
      title: '时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '置顶',
      dataIndex: 'is_top',
      key: 'is_top',
      render: (v: boolean) => (v ? <Tag color="volcano">置顶</Tag> : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: InfoStatus) => {
        const label = labels[s]
        return <Tag color={label?.color}>{label?.text ?? s}</Tag>
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: InformationAdminPost) => (
        <div className="flex gap-1 flex-wrap">
          <Button size="small" onClick={() => setDetail(record)}>
            详情
          </Button>
          {(record.status === 'pending' || record.status === 'rejected') && (
            <>
              <Button
                size="small"
                type="primary"
                onClick={() => {
                  setReviewApproved(true)
                  setReviewTarget(record)
                }}
              >
                通过
              </Button>
              <Button
                size="small"
                danger
                onClick={() => {
                  setReviewApproved(false)
                  setReviewTarget(record)
                }}
              >
                驳回
              </Button>
            </>
          )}
          {record.status === 'approved' &&
            (record.is_top ? (
              <Popconfirm title="取消置顶？" onConfirm={() => toggleTop(record, false)}>
                <Button size="small">取消置顶</Button>
              </Popconfirm>
            ) : (
              <Popconfirm title="设为置顶？" onConfirm={() => toggleTop(record, true)}>
                <Button size="small" type="primary" ghost style={{ color: MALL_PRIMARY, borderColor: MALL_PRIMARY }}>
                  置顶
                </Button>
              </Popconfirm>
            ))}
        </div>
      ),
    },
  ]

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        信息发布审核
      </h3>
      <Tabs
        activeKey={status}
        items={TABS}
        onChange={(key) => setStatus(key as InfoStatus | '')}
        className="mb-2"
      />
      <div className="mb-3" style={{ maxWidth: 280 }}>
        <Input.Search
          placeholder="搜索标题 / 内容 / 联系人 / 电话"
          allowClear
          onSearch={setKeyword}
        />
      </div>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={{
          current: page,
          pageSize: 10,
          total,
          onChange: setPage,
          showSizeChanger: false,
        }}
      />

      <Modal
        title={reviewApproved ? '通过信息审核' : '驳回信息'}
        open={reviewTarget != null}
        onCancel={() => setReviewTarget(null)}
        onOk={submitReview}
        confirmLoading={submitting}
        okText="确认"
        cancelText="取消"
      >
        {reviewApproved ? (
          <p className="text-sm" style={{ color: '#666' }}>
            通过后「{reviewTarget?.title}」将在信息中心公开可见。
          </p>
        ) : (
          <Form form={form} layout="vertical" className="mt-4">
            <Form.Item
              name="reject_reason"
              label="驳回原因"
              rules={[
                { required: true, message: '请填写驳回原因' },
                { max: 200 },
              ]}
            >
              <Input.TextArea rows={3} placeholder="如：内容与所选分类不符" />
            </Form.Item>
          </Form>
        )}
      </Modal>

      <Drawer
        title="信息详情"
        width={560}
        open={detail != null}
        onClose={() => setDetail(null)}
      >
        {detail && (
          <Descriptions column={1} size="small" bordered>
            <Descriptions.Item label="标题">{detail.title}</Descriptions.Item>
            <Descriptions.Item label="分类">{detail.category_name}</Descriptions.Item>
            <Descriptions.Item label="价格">{detail.price || '面议'}</Descriptions.Item>
            <Descriptions.Item label="发布人 ID">{detail.poster_user_id}</Descriptions.Item>
            <Descriptions.Item label="发布人">{detail.poster_username}</Descriptions.Item>
            <Descriptions.Item label="实名记录编号">{detail.publisher_verification_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="实名姓名">{detail.publisher_real_name || '-'}</Descriptions.Item>
            <Descriptions.Item label="证件号码">{detail.publisher_document_number_masked || '-'}</Descriptions.Item>
            <Descriptions.Item label="实名有效">
              <Tag color={detail.publisher_verification_valid ? 'green' : 'red'}>
                {detail.publisher_verification_valid ? '有效' : '无效或缺失'}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="联系人">{detail.contact_name}</Descriptions.Item>
            <Descriptions.Item label="联系电话">{detail.contact_phone || '-'}</Descriptions.Item>
            <Descriptions.Item label="发布时间">
              {dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}
            </Descriptions.Item>
            <Descriptions.Item label="浏览量">{detail.view_count}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={labels[detail.status]?.color}>{labels[detail.status]?.text}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="驳回原因">{detail.reject_reason || '-'}</Descriptions.Item>
            {detail.attributes && Object.keys(detail.attributes).length > 0 && (
              <Descriptions.Item label="属性">
                <div className="space-y-1">
                  {Object.entries(detail.attributes).map(([key, value]) => (
                    <div key={key}>
                      {key}：{value}
                    </div>
                  ))}
                </div>
              </Descriptions.Item>
            )}
            <Descriptions.Item label="详情内容">
              <div style={{ whiteSpace: 'pre-wrap' }}>{detail.content}</div>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>
    </div>
  )
}
