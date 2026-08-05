import api from './api'
import type { AdminNotification, AdminNotificationListResponse, AdminNotificationPayload, AdminNotificationPublished, Notification, NotificationListResponse, NotificationRecipient, NotificationSummary } from './types'
export const listNotifications = async (offset = 0, limit = 20) => (await api.get<NotificationListResponse>('/notifications', { params: { offset, limit } })).data
export const notificationSummary = async () => (await api.get<NotificationSummary>('/notifications/summary')).data
export const getNotification = async (id: string) => (await api.get<Notification>(`/notifications/${id}`)).data
export const markNotificationRead = async (id: string) => { await api.post(`/notifications/${id}/read`) }
export const markAllNotificationsRead = async () => (await api.post<{ marked_count: number }>('/notifications/read-all')).data
export const listNotificationRecipients = async () => (await api.get<NotificationRecipient[]>('/admin/notifications/recipients')).data
export const publishNotification = async (payload: AdminNotificationPayload) => (await api.post<AdminNotificationPublished>('/admin/notifications', payload)).data
export const listPublishedNotifications = async () => (await api.get<AdminNotificationListResponse>('/admin/notifications')).data
export const updatePublishedNotification = async (id: string, payload: Pick<AdminNotification, 'title' | 'body_markdown'>) => (await api.patch<AdminNotification>(`/admin/notifications/${id}`, payload)).data
