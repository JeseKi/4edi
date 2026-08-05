import { Alert, App, Button, Card, DatePicker, Descriptions, Drawer, Flex, Input, Select, Space, Table, Tag, Typography } from 'antd'
import { AuditOutlined, ReloadOutlined } from '@ant-design/icons'
import type { TableColumnsType } from 'antd'
import type { Dayjs } from 'dayjs'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { listAuditEvents } from '../../../lib/admin'
import type { AdminAuditEvent, AuditMethod, AuditOutcome } from '../../../lib/types'
import { resolveApiErrorMessage } from '../../../lib/error'

const { RangePicker } = DatePicker

const outcomeOptions = [
  { value: 'success', label: '成功' },
  { value: 'failure', label: '失败' },
]

const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map((value) => ({
  value,
  label: value,
}))

type DateRange = [Dayjs | null, Dayjs | null] | null

export default function AuditLogPage() {
  const { message } = App.useApp()
  const [isMobile, setIsMobile] = useState(false)
  const [items, setItems] = useState<AdminAuditEvent[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [keyword, setKeyword] = useState('')
  const [outcome, setOutcome] = useState<AuditOutcome | undefined>()
  const [method, setMethod] = useState<AuditMethod | undefined>()
  const [resourceType, setResourceType] = useState('')
  const [dateRange, setDateRange] = useState<DateRange>(null)
  const [selectedEvent, setSelectedEvent] = useState<AdminAuditEvent | null>(null)

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth < 768)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  const loadEvents = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listAuditEvents({
        page,
        page_size: pageSize,
        q: keyword.trim() || undefined,
        outcome,
        method,
        resource_type: resourceType.trim() || undefined,
        created_from: dateRange?.[0]?.toISOString(),
        created_to: dateRange?.[1]?.toISOString(),
      })
      setItems(data.items)
      setTotal(data.total)
    } catch (err) {
      const text = resolveApiErrorMessage(err, '请求失败，请稍后再试。')
      setError(text)
      message.error(text)
    } finally {
      setLoading(false)
    }
  }, [dateRange, keyword, message, method, outcome, page, pageSize, resourceType])

  useEffect(() => {
    void loadEvents()
  }, [loadEvents])

  const resetToFirstPage = useCallback(() => {
    setPage(1)
  }, [])

  const columns: TableColumnsType<AdminAuditEvent> = useMemo(
    () => [
      {
        title: '时间',
        dataIndex: 'created_at',
        key: 'created_at',
        render: (value: string) => new Date(value).toLocaleString(),
        width: 180,
      },
      {
        title: '结果',
        dataIndex: 'outcome',
        key: 'outcome',
        render: (value: AuditOutcome, record) => (
          <Space direction="vertical" size={0}>
            <Tag color={value === 'success' ? 'green' : 'red'}>
              {value === 'success' ? '成功' : '失败'}
            </Tag>
            {record.http_status_code && (
              <Typography.Text type="secondary">{record.http_status_code}</Typography.Text>
            )}
          </Space>
        ),
        width: 100,
      },
      {
        title: '优先级',
        dataIndex: 'priority',
        key: 'priority',
        render: (value: 'high' | 'low') => (
          <Tag color={value === 'high' ? 'red' : 'blue'}>{value === 'high' ? '高' : '低'}</Tag>
        ),
        width: 90,
      },
      {
        title: '动作',
        key: 'action',
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text strong>{record.action_label ?? record.action}</Typography.Text>
            <Typography.Text type="secondary">
              {[record.action, [record.method, record.path_template ?? record.path].filter(Boolean).join(' ')].join(' · ')}
            </Typography.Text>
          </Space>
        ),
      },
      {
        title: '操作者',
        key: 'actor',
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{record.actor_username ?? record.actor_identifier ?? '-'}</Typography.Text>
            {record.actor_user_id && (
              <Typography.Text type="secondary">ID {record.actor_user_id}</Typography.Text>
            )}
          </Space>
        ),
        width: 150,
      },
      {
        title: '目标',
        key: 'target',
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{record.target_summary ?? record.resource_id ?? '-'}</Typography.Text>
            {record.resource_type && <Typography.Text type="secondary">{record.resource_type}</Typography.Text>}
          </Space>
        ),
      },
      {
        title: '来源',
        key: 'source',
        render: (_, record) => (
          <Space direction="vertical" size={0}>
            <Typography.Text>{record.client_ip ?? '-'}</Typography.Text>
            {record.duration_ms !== null && (
              <Typography.Text type="secondary">{record.duration_ms} ms</Typography.Text>
            )}
          </Space>
        ),
        width: 130,
      },
      {
        title: '操作',
        key: 'actions',
        render: (_, record) => (
          <Button size="small" onClick={() => setSelectedEvent(record)}>
            详情
          </Button>
        ),
        width: 90,
      },
    ],
    [],
  )

  return (
    <Flex vertical gap={24}>
      <Card>
        <Flex align={isMobile ? 'stretch' : 'center'} justify="space-between" wrap="wrap" gap={16} vertical={isMobile}>
          <Space>
            <AuditOutlined style={{ fontSize: 20 }} />
            <Typography.Title level={4} style={{ margin: 0 }}>
              审计日志
            </Typography.Title>
          </Space>
          <Button icon={<ReloadOutlined />} onClick={loadEvents} loading={loading}>
            {isMobile ? '' : '刷新'}
          </Button>
        </Flex>
        <Flex wrap="wrap" gap={8} className="mt-4">
          <Input.Search
            placeholder="搜索动作 / 路径 / 操作者 / 目标 / request id"
            value={keyword}
            onChange={(event) => setKeyword(event.target.value)}
            onSearch={() => {
              resetToFirstPage()
              void loadEvents()
            }}
            allowClear
            style={{ minWidth: isMobile ? '100%' : 320, flex: isMobile ? 1 : 'none' }}
          />
          <Select
            placeholder="结果"
            value={outcome}
            onChange={(value) => {
              setOutcome(value)
              resetToFirstPage()
            }}
            options={outcomeOptions}
            allowClear
            style={{ width: 120 }}
          />
          <Select
            placeholder="方法"
            value={method}
            onChange={(value) => {
              setMethod(value)
              resetToFirstPage()
            }}
            options={methodOptions}
            allowClear
            style={{ width: 120 }}
          />
          <Input
            placeholder="资源类型"
            value={resourceType}
            onChange={(event) => {
              setResourceType(event.target.value)
              resetToFirstPage()
            }}
            allowClear
            style={{ width: 160 }}
          />
          <RangePicker
            showTime
            value={dateRange}
            onChange={(value) => {
              setDateRange(value)
              resetToFirstPage()
            }}
            style={{ minWidth: isMobile ? '100%' : 360 }}
          />
        </Flex>
      </Card>

      {error && <Alert type="error" showIcon message={error} />}

      <Card bodyStyle={{ padding: 0 }}>
        <Table
          columns={columns}
          dataSource={items}
          rowKey="id"
          loading={loading}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            onChange: (nextPage, nextPageSize) => {
              setPage(nextPage)
              setPageSize(nextPageSize)
            },
          }}
          locale={{ emptyText: '暂无审计日志' }}
          scroll={{ x: 'max-content' }}
        />
      </Card>

      <Drawer
        title="审计详情"
        open={Boolean(selectedEvent)}
        onClose={() => setSelectedEvent(null)}
        width={isMobile ? '100%' : 640}
      >
        {selectedEvent && (
          <Flex vertical gap={16}>
            <Descriptions column={1} size="small" bordered>
              <Descriptions.Item label="动作">
                {selectedEvent.action_label
                  ? `${selectedEvent.action_label} (${selectedEvent.action})`
                  : selectedEvent.action}
              </Descriptions.Item>
              <Descriptions.Item label="结果">
                {selectedEvent.outcome === 'success' ? '成功' : '失败'}
              </Descriptions.Item>
              <Descriptions.Item label="路径">{selectedEvent.path ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="操作者">
                {selectedEvent.actor_username ?? selectedEvent.actor_identifier ?? '-'}
              </Descriptions.Item>
              <Descriptions.Item label="目标">
                {[selectedEvent.resource_type, selectedEvent.resource_id, selectedEvent.target_summary]
                  .filter(Boolean)
                  .join(' / ') || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="Request ID">{selectedEvent.request_id ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="User Agent">{selectedEvent.user_agent ?? '-'}</Descriptions.Item>
            </Descriptions>
            <Typography.Text strong>脱敏详情</Typography.Text>
            <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(selectedEvent.detail, null, 2)}
            </pre>
          </Flex>
        )}
      </Drawer>
    </Flex>
  )
}
