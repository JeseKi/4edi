import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { App, Badge, Button, ConfigProvider, Dropdown, Input, Space } from 'antd'
import {
  SearchOutlined,
  ShoppingCartOutlined,
  UserOutlined,
} from '@ant-design/icons'
import { useAuth } from '../../hooks/useAuth'
import { listMallCart } from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'

const MALL_PRIMARY = '#F31947'

export default function MallLayout() {
  const { user, isAuthenticated, logout } = useAuth()
  const { message } = App.useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const [keyword, setKeyword] = useState('')
  const [cartCount, setCartCount] = useState(0)

  useEffect(() => {
    let cancelled = false
    if (isAuthenticated && location.pathname !== '/mall/checkout') {
      listMallCart()
        .then((items) => {
          if (!cancelled) setCartCount(items.reduce((sum, item) => sum + item.quantity, 0))
        })
        .catch(() => {
          // 购物车数量加载失败不阻塞页面
        })
    } else {
      setCartCount(0)
    }
    return () => {
      cancelled = true
    }
  }, [isAuthenticated, location.pathname])

  const onSearch = () => {
    navigate(`/mall?keyword=${encodeURIComponent(keyword.trim())}`)
  }

  const onLogout = async () => {
    try {
      await logout()
      message.success('已退出登录')
      navigate('/login', { replace: true })
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '退出登录失败'))
    }
  }

  const userMenu = {
    items: [
      { key: 'orders', label: <Link to="/mall/orders">我的订单</Link> },
      { key: 'refunds', label: <Link to="/mall/refunds">退款 / 售后</Link> },
      { key: 'evaluations', label: <Link to="/mall/evaluations">评价中心</Link> },
      { key: 'coupons', label: <Link to="/mall/coupons">领券中心</Link> },
      { key: 'favorites', label: <Link to="/mall/favorites">我的收藏</Link> },
      { key: 'footprints', label: <Link to="/mall/footprints">浏览足迹</Link> },
      { key: 'chat', label: <Link to="/mall/chat">在线客服</Link> },
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
            <Link to="/mall" className="flex items-center shrink-0">
              <span className="text-xl font-bold" style={{ color: MALL_PRIMARY }}>
                沐泽商城
              </span>
            </Link>
            <div className="flex items-center flex-1 max-w-[480px]">
              <Input.Search
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onSearch={onSearch}
                placeholder="搜索商品"
                enterButton={<SearchOutlined />}
                style={{ borderRadius: 4 }}
                allowClear
              />
            </div>
            <nav className="flex items-center gap-5 ml-auto text-sm">
              <Link to="/mall" className="hover:opacity-80">
                首页
              </Link>
              <Link to="/mall/orders" className="hover:opacity-80">
                我的订单
              </Link>
              <Link to="/mall/chat" className="hover:opacity-80">
                在线客服
              </Link>
              <Link to="/mall/seller/shop" className="hover:opacity-80">
                申请开店
              </Link>
              <Badge count={cartCount} size="small" color={MALL_PRIMARY}>
                <Button
                  type="text"
                  icon={<ShoppingCartOutlined />}
                  onClick={() => navigate(isAuthenticated ? '/mall/cart' : '/login')}
                >
                  购物车
                </Button>
              </Badge>
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
                    <Button type="primary" size="small" style={{ background: MALL_PRIMARY }}>
                      注册
                    </Button>
                  </Link>
                </Space>
              )}
            </nav>
          </div>
        </header>

        <main className="flex-1 w-full mx-auto px-4 py-4" style={{ maxWidth: 1184 }}>
          <Outlet />
        </main>

        <footer className="text-center text-xs py-6" style={{ color: '#999', background: '#fff' }}>
          沐泽商城 ·{' '}
          <a
            href="https://beian.miit.gov.cn/"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#999' }}
          >
            浙ICP备2026035190号-1
          </a>
        </footer>
      </div>
    </ConfigProvider>
  )
}
