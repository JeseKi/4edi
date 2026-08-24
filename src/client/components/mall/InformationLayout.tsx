import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { App, ConfigProvider, Dropdown, Space } from 'antd'
import { UserOutlined } from '@ant-design/icons'
import { useAuth } from '../../hooks/useAuth'
import { resolveApiErrorMessage } from '../../lib/error'
import InformationFooter from './InformationFooter'

const MALL_PRIMARY = '#F31947'

export default function InformationLayout() {
  const { user, isAuthenticated, logout } = useAuth()
  const { message } = App.useApp()
  const navigate = useNavigate()
  const location = useLocation()

  const onLogout = async () => {
    try {
      await logout()
      message.success('已退出登录')
      navigate('/login', { replace: true })
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '退出登录失败'))
    }
  }

  const requireLogin = () => {
    if (!isAuthenticated) {
      navigate('/login', {
        state: {
          from: { pathname: location.pathname, search: location.search },
        },
      })
      return false
    }
    return true
  }

  const userMenu = {
    items: [
      { key: 'mine', label: <Link to="/mall/information/mine">我的发布</Link> },
      { key: 'logout', label: '退出登录', danger: true },
    ],
    onClick: ({ key }: { key: string }) => {
      if (key === 'logout') onLogout()
    },
  }

  return (
    <ConfigProvider
      theme={{
        token: { colorPrimary: MALL_PRIMARY },
      }}
    >
      <div className="min-h-screen flex flex-col" style={{ background: '#F5F5F7' }}>
        <header
          className="sticky top-0 z-50"
          style={{ background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}
        >
          <div
            className="mx-auto flex items-center gap-6 px-4"
            style={{ maxWidth: 1184, height: 64 }}
          >
            <Link to="/mall/information" className="flex items-center shrink-0">
              <span className="text-xl font-bold" style={{ color: MALL_PRIMARY }}>
                沐泽健康
              </span>
            </Link>
            <nav className="flex items-center gap-5 ml-auto text-sm">
              <Link to="/mall/information" className="hover:opacity-80">
                信息广场
              </Link>
              <Link
                to="/mall/information/post"
                className="hover:opacity-80"
                onClick={(e) => {
                  if (!requireLogin()) e.preventDefault()
                }}
              >
                发布信息
              </Link>
              <Link
                to="/mall/information/mine"
                className="hover:opacity-80"
                onClick={(e) => {
                  if (!requireLogin()) e.preventDefault()
                }}
              >
                我的发布
              </Link>
              <Link to="/mall/complaint" className="hover:opacity-80">
                投诉与帮助
              </Link>
              {isAuthenticated ? (
                <Dropdown menu={userMenu} placement="bottomRight">
                  <Space className="cursor-pointer hover:opacity-80">
                    <UserOutlined />
                    <span>{user?.username}</span>
                  </Space>
                </Dropdown>
              ) : (
                <Space>
                  <Link to="/login">登录</Link>
                  <Link to="/register">
                    <button
                      type="button"
                      className="text-white text-xs px-3 py-1 rounded"
                      style={{ background: MALL_PRIMARY }}
                    >
                      注册
                    </button>
                  </Link>
                </Space>
              )}
            </nav>
          </div>
        </header>

        <main className="flex-1 w-full mx-auto px-4 py-4" style={{ maxWidth: 1184 }}>
          <Outlet />
        </main>

        <InformationFooter />
      </div>
    </ConfigProvider>
  )
}
