import { App, Button, Card, Empty, Flex, List, Pagination, Spin, Typography } from 'antd'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import NotificationMarkdown from '../../components/notifications/NotificationMarkdown'
import { listNotifications, markAllNotificationsRead, markNotificationRead } from '../../lib/notifications'
import type { Notification } from '../../lib/types'

export default function NotificationInboxPage() {
  const { message } = App.useApp()
  const navigate = useNavigate()
  const [items, setItems] = useState<Notification[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768)
  const selected = items.find((item) => item.id === selectedId) ?? null

  const load = useCallback(async (nextOffset = 0) => {
    setLoading(true)
    try {
      const data = await listNotifications(nextOffset)
      setItems(data.items)
      setTotal(data.total)
      setOffset(nextOffset)
      setSelectedId((current) => current ?? data.items.find((item) => !item.read_at)?.id ?? data.items[0]?.id ?? null)
    } finally { setLoading(false) }
  }, [])
  useEffect(() => { void load(0) }, [load])
  useEffect(() => { const update = () => setIsMobile(window.innerWidth < 768); window.addEventListener('resize', update); return () => window.removeEventListener('resize', update) }, [])

  const open = async (item: Notification) => {
    if (isMobile) { navigate(`/notifications/${item.id}`); return }
    setSelectedId(item.id)
    if (!item.read_at) {
      await markNotificationRead(item.id)
      setItems((current) => current.map((value) => value.id === item.id ? { ...value, read_at: new Date().toISOString() } : value))
      window.dispatchEvent(new Event('notification-updated'))
    }
  }
  const readAll = async () => { const result = await markAllNotificationsRead(); message.success(`已标记 ${result.marked_count} 条消息为已读`); window.dispatchEvent(new Event('notification-updated')); void load(offset) }
  const list = loading ? <Spin /> : items.length === 0 ? <Empty description="暂无消息" /> : <List dataSource={items} renderItem={(item) => <List.Item className={item.id === selectedId ? 'notification-row-selected' : undefined} onClick={() => void open(item)} style={{ cursor: 'pointer', paddingInline: 16 }}><List.Item.Meta title={<Typography.Text strong={!item.read_at}>{item.title}</Typography.Text>} description={<><Typography.Text type="secondary">{new Date(item.created_at).toLocaleString()}</Typography.Text><div className="notification-row-preview">{item.body_markdown.replaceAll('*', '').replaceAll('_', '').replaceAll('#', '').replaceAll('`', '').replaceAll('>', '').slice(0, 90)}</div></>} /></List.Item>} />
  return <Flex vertical gap={16}><Flex justify="space-between" align="center"><Typography.Title level={3} style={{ margin: 0 }}>站内消息</Typography.Title><Button onClick={readAll}>全部标为已读</Button></Flex><Card bodyStyle={{ padding: 0 }}><div className="notification-inbox-layout"><div className="notification-inbox-list">{list}</div><div className="notification-inbox-detail">{selected ? <><Typography.Title level={3}>{selected.title}</Typography.Title><Typography.Paragraph type="secondary">{new Date(selected.created_at).toLocaleString()}</Typography.Paragraph><NotificationMarkdown content={selected.body_markdown} /></> : <Empty description="选择一条消息查看详情" />}</div></div></Card>{total > 20 && <Pagination current={offset / 20 + 1} total={total} pageSize={20} onChange={(page) => void load((page - 1) * 20)} />}</Flex>
}
