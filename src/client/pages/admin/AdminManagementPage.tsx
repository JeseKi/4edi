import { ApiOutlined, AuditOutlined, KeyOutlined, LockOutlined, TeamOutlined, BellOutlined } from '@ant-design/icons'
import { Tabs } from 'antd'
import UserManagementPage from './UserManagementPage'
import PermissionManagementPage from './PermissionManagementPage'
import ScopeManagementPage from './ScopeManagementPage'
import OAuthClientManagementPage from './OAuthClientManagementPage'
import AuditLogPage from './AuditLogPage'
import NotificationManagementPage from './NotificationManagementPage'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'

export default function AdminManagementPage() {
  const { features } = useRuntimeConfig()
  const enabled = new Set(features)
  const tabItems = [
  {
    key: 'users',
    label: (
      <span>
        <TeamOutlined />
        用户管理
      </span>
    ),
    children: <UserManagementPage />,
  },
  {
    key: 'scopes',
    label: (
      <span>
        <LockOutlined />
        Scope 管理
      </span>
    ),
    children: <ScopeManagementPage />,
  },
  {
    key: 'permissions',
    label: (
      <span>
        <KeyOutlined />
        权限管理
      </span>
    ),
    children: <PermissionManagementPage />,
  },
  ...(enabled.has('oauth-provider') ? [{
    key: 'oauth-clients',
    label: (
      <span>
        <ApiOutlined />
        OAuth Clients
      </span>
    ),
    children: <OAuthClientManagementPage />,
  }] : []),
  ...(enabled.has('audit') ? [{
    key: 'audit',
    label: (
      <span>
        <AuditOutlined />
        审计日志
      </span>
    ),
    children: <AuditLogPage />,
  }] : []),
  ...(enabled.has('notifications') ? [{ key: 'notifications', label: <span><BellOutlined />站内消息</span>, children: <NotificationManagementPage /> }] : []),
  ]

  return (
    <div style={{ overflowX: 'auto' }}>
      <Tabs defaultActiveKey="users" items={tabItems} style={{ minWidth: 500 }} />
    </div>
  )
}
