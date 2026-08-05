import { Alert, Card, Spin, Typography } from 'antd'
import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import NotificationMarkdown from '../../components/notifications/NotificationMarkdown'
import { getNotification, markNotificationRead } from '../../lib/notifications'
import type { Notification } from '../../lib/types'
export default function NotificationDetailPage() { const { id } = useParams(); const [item, setItem] = useState<Notification | null>(null); const [error, setError] = useState<string | null>(null); useEffect(() => { if (!id) return; void getNotification(id).then((value) => { setItem(value); if (!value.read_at) void markNotificationRead(value.id) }).catch(() => setError('消息不存在或无权查看')) }, [id]); if (error) return <Alert type="error" message={error} />; if (!item) return <Spin />; return <Card><Typography.Title level={3}>{item.title}</Typography.Title><Typography.Paragraph type="secondary">{new Date(item.created_at).toLocaleString()}</Typography.Paragraph><NotificationMarkdown content={item.body_markdown} /></Card> }
