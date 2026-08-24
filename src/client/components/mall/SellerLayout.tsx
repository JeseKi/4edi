import { Link, NavLink, Outlet } from 'react-router-dom'
import { Badge, ConfigProvider } from 'antd'
import {
  AppstoreOutlined,
  MessageOutlined,
  ProfileOutlined,
  ShopOutlined,
  StarOutlined,
  GiftOutlined,
  WalletOutlined,
  UndoOutlined,
} from '@ant-design/icons'
import { useAuth } from '../../hooks/useAuth'

const MENUS = [
  { key: 'shop', path: '/mall/seller/shop', label: '店铺管理', icon: <ShopOutlined /> },
  { key: 'goods', path: '/mall/seller/goods', label: '商品管理', icon: <AppstoreOutlined /> },
  { key: 'orders', path: '/mall/seller/orders', label: '订单管理', icon: <ProfileOutlined /> },
  { key: 'refunds', path: '/mall/seller/refunds', label: '退款管理', icon: <UndoOutlined /> },
  { key: 'evaluations', path: '/mall/seller/evaluations', label: '评价管理', icon: <StarOutlined /> },
  { key: 'coupons', path: '/mall/seller/coupons', label: '优惠券', icon: <GiftOutlined /> },
  { key: 'wallet', path: '/mall/seller/wallet', label: '资金钱包', icon: <WalletOutlined /> },
  { key: 'chat', path: '/mall/seller/chat', label: '客服消息', icon: <MessageOutlined /> },
]

export default function SellerLayout() {
  const { user } = useAuth()

  return (
    <ConfigProvider
      theme={{
        token: { colorPrimary: '#F31947' },
      }}
    >
      <div className="min-h-screen flex flex-col" style={{ background: '#F5F5F7' }}>
        <header
          className="sticky top-0 z-50"
          style={{ background: '#fff', boxShadow: '0 1px 4px rgba(0,0,0,0.08)' }}
        >
          <div className="mx-auto flex items-center justify-between px-4" style={{ maxWidth: 1184, height: 56 }}>
            <div className="flex items-center gap-6">
              <Link to="/mall" className="text-lg font-bold" style={{ color: '#F31947' }}>
                沐泽健康
              </Link>
              <span className="text-sm" style={{ color: '#333' }}>
                商家中心
              </span>
              <Badge count="卖家" color="#F31947" offset={[-2, 2]}>
                <span className="text-xs px-2 py-0.5 rounded" style={{ background: '#fff5f6', color: '#F31947' }}>
                  {user?.username}
                </span>
              </Badge>
            </div>
            <Link to="/mall" className="text-sm hover:opacity-80" style={{ color: '#666' }}>
              返回商城首页
            </Link>
          </div>
        </header>

        <div className="mx-auto flex gap-4 w-full px-4 py-4" style={{ maxWidth: 1184 }}>
          <aside
            className="shrink-0 rounded bg-white"
            style={{ width: 180, padding: '12px 8px', alignSelf: 'flex-start' }}
          >
            {MENUS.map((menu) => (
              <NavLink
                key={menu.key}
                to={menu.path}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-2.5 rounded text-sm mb-1 ${
                    isActive ? 'font-medium' : ''
                  }`
                }
                style={({ isActive }) => ({
                  color: isActive ? '#F31947' : '#555',
                  background: isActive ? '#fff5f6' : 'transparent',
                })}
              >
                {menu.icon}
                {menu.label}
              </NavLink>
            ))}
          </aside>
          <main className="flex-1 min-w-0">
            <Outlet />
          </main>
        </div>
      </div>
    </ConfigProvider>
  )
}
