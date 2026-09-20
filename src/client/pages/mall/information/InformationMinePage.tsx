import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { App, Button, Empty, Popconfirm, Spin, Tag } from 'antd'
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { deleteInformation, listMyInformation } from '../../../lib/information'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { InfoStatus, InformationMinePost } from '../../../lib/types'

const MALL_PRIMARY = '#F31947'

const STATUS_LABELS: Record<InfoStatus, { text: string; color: string }> = {
  pending: { text: '待审核', color: 'orange' },
  approved: { text: '已通过', color: 'green' },
  rejected: { text: '已驳回', color: 'red' },
}

export default function InformationMinePage() {
  const { message } = App.useApp()
  const [items, setItems] = useState<InformationMinePost[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setItems(await listMyInformation())
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '加载失败'))
    } finally {
      setLoading(false)
    }
  }, [message])

  useEffect(() => {
    load()
  }, [load])

  const remove = async (postId: number) => {
    try {
      await deleteInformation(postId)
      message.success('已删除')
      setItems((prev) => prev.filter((item) => item.id !== postId))
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '删除失败'))
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="text-base font-bold" style={{ color: '#333' }}>
          我的发布
        </div>
        <Link to="/mall/information/post">
          <Button type="primary" icon={<PlusOutlined />} style={{ background: MALL_PRIMARY }}>
            发布信息
          </Button>
        </Link>
      </div>

      {loading ? (
        <div className="flex justify-center py-24">
          <Spin size="large" />
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-lg bg-white py-16">
          <Empty description="你还没有发布过信息">
            <Link to="/mall/information/post">
              <Button type="primary" style={{ background: MALL_PRIMARY }}>
                去发布
              </Button>
            </Link>
          </Empty>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => {
            const status = STATUS_LABELS[item.status]
            return (
              <div key={item.id} className="rounded-lg bg-white p-5">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <Tag color={status.color} style={{ marginInlineEnd: 0 }}>
                        {status.text}
                      </Tag>
                      {item.is_top && (
                        <Tag color="volcano" style={{ marginInlineEnd: 0 }}>
                          置顶
                        </Tag>
                      )}
                      <span className="font-medium" style={{ color: '#222' }}>
                        {item.title}
                      </span>
                    </div>
                    <div className="text-xs mt-1" style={{ color: '#999' }}>
                      {item.category_name} · 发布于 {dayjs(item.created_at).format('YYYY-MM-DD HH:mm')} ·{' '}
                      联系人 {item.contact_name} · 电话 {item.contact_phone || '未填写'}
                    </div>
                    {item.status === 'rejected' && item.reject_reason && (
                      <div className="text-xs mt-2" style={{ color: '#cf1322' }}>
                        驳回原因：{item.reject_reason}
                      </div>
                    )}
                    {item.status === 'pending' && (
                      <div className="text-xs mt-2" style={{ color: '#ad6800' }}>
                        平台将在 1 个工作日内完成审核，请留意审核结果。
                      </div>
                    )}
                    {item.reviewed_at && item.status !== 'pending' && (
                      <div className="text-xs mt-2" style={{ color: '#777' }}>
                        审核时间：{dayjs(item.reviewed_at).format('YYYY-MM-DD HH:mm')}
                      </div>
                    )}
                    {item.status === 'approved' && (
                      <div className="mt-2">
                        <Link
                          to={`/mall/information/${item.id}`}
                          className="text-xs"
                          style={{ color: MALL_PRIMARY }}
                        >
                          查看公开页 →
                        </Link>
                      </div>
                    )}
                  </div>
                  <Popconfirm
                    title="确定删除这条信息？"
                    okText="删除"
                    cancelText="取消"
                    onConfirm={() => remove(item.id)}
                  >
                    <Button danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
