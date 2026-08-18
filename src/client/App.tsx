import { BrowserRouter as Router, Navigate, Route, Routes } from 'react-router-dom'
import MainLayout from './components/layout/MainLayout'
import DashboardPage from './pages/dashboard/DashboardPage'
import ExamplePage from './pages/dashboard/ExamplePage'
import ProfilePage from './pages/profile/ProfilePage'
import SecurityPage from './pages/profile/SecurityPage'
import DevicesPage from './pages/profile/DevicesPage'
import AdminManagementPage from './pages/admin/AdminManagementPage'
import LoginPage from './pages/auth/LoginPage'
import ConfirmPasswordChangePage from './pages/auth/ConfirmPasswordChangePage'
import RegisterPage from './pages/auth/RegisterPage'
import ResetPasswordPage from './pages/auth/ResetPasswordPage'
import OAuthAuthorizePage from './pages/auth/OAuthAuthorizePage'
import OAuthDeviceAuthorizePage from './pages/auth/OAuthDeviceAuthorizePage'
import LandingPage from './pages/landing/LandingPage'
import NotificationInboxPage from './pages/notifications/NotificationInboxPage'
import NotificationDetailPage from './pages/notifications/NotificationDetailPage'
import MallLayout from './components/mall/MallLayout'
import MallHomePage from './pages/mall/HomePage'
import GoodsDetailPage from './pages/mall/GoodsDetailPage'
import CartPage from './pages/mall/CartPage'
import CheckoutPage from './pages/mall/CheckoutPage'
import OrdersPage from './pages/mall/OrdersPage'
import OrderDetailPage from './pages/mall/OrderDetailPage'
import RefundListPage from './pages/mall/RefundListPage'
import EvaluationCenterPage from './pages/mall/EvaluationCenterPage'
import CouponCenterPage from './pages/mall/CouponCenterPage'
import FavoritesPage from './pages/mall/FavoritesPage'
import FootprintsPage from './pages/mall/FootprintsPage'
import ChatPage from './pages/mall/ChatPage'
import HelpCenterPage from './pages/mall/HelpCenterPage'
import SiteInfoPage from './pages/mall/SiteInfoPage'
import SellerLayout from './components/mall/SellerLayout'
import ShopManagePage from './pages/mall/seller/ShopManagePage'
import GoodsManagePage from './pages/mall/seller/GoodsManagePage'
import OrdersManagePage from './pages/mall/seller/OrdersManagePage'
import RefundManagePage from './pages/mall/seller/RefundManagePage'
import EvaluationManagePage from './pages/mall/seller/EvaluationManagePage'
import CouponManagePage from './pages/mall/seller/CouponManagePage'
import WalletPage from './pages/mall/seller/WalletPage'
import SellerChatPage from './pages/mall/seller/SellerChatPage'
import ShopReviewPage from './pages/mall/admin/ShopReviewPage'
import WithdrawReviewPage from './pages/mall/admin/WithdrawReviewPage'
import CouponAdminPage from './pages/mall/admin/CouponAdminPage'
import { AuthProvider, RequireAdmin, RequireAuth } from './providers/AuthProvider'
import { RuntimeConfigProvider } from './providers/RuntimeConfigProvider'
import ThemeToggle from './components/theme/ThemeToggle'
import { useRuntimeConfig } from './hooks/useRuntimeConfig'

function AppRoutes() {
  const { loading, features } = useRuntimeConfig()
  const enabled = new Set(features)

  if (loading) {
    return null
  }

  const hasFeature = (name: string) => enabled.has(name)

  return (
    <>
      <Routes>
        <Route
          path="/"
          element={
            hasFeature('mall') ? (
              <Navigate to="/mall" replace />
            ) : (
              <LandingPage />
            )
          }
        />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/reset-password/:token" element={<ResetPasswordPage />} />
        <Route path="/profile/password-change/:token" element={<ConfirmPasswordChangePage />} />
        {hasFeature('oauth-provider') && (
          <Route
            path="/oauth/authorize"
            element={<RequireAuth><OAuthAuthorizePage /></RequireAuth>}
          />
        )}
        {hasFeature('oauth-provider') && (
          <Route
            path="/oauth/device"
            element={<RequireAuth><OAuthDeviceAuthorizePage /></RequireAuth>}
          />
        )}
        <Route element={<RequireAuth><MainLayout /></RequireAuth>}>
          <Route path="/dashboard" element={<DashboardPage />} />
          {hasFeature('example') && <Route path="/example" element={<ExamplePage />} />}
          {hasFeature('notifications') && <Route path="/notifications" element={<NotificationInboxPage />} />}
          {hasFeature('notifications') && <Route path="/notifications/:id" element={<NotificationDetailPage />} />}
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/profile/security" element={<SecurityPage />} />
          <Route path="/profile/devices" element={<DevicesPage />} />
          {hasFeature('admin') && (
            <Route path="/admin" element={<RequireAdmin><AdminManagementPage /></RequireAdmin>} />
          )}
        </Route>
        {hasFeature('mall') && (
          <Route element={<MallLayout />}>
            <Route path="/mall" element={<MallHomePage />} />
            <Route path="/mall/goods/:goodsId" element={<GoodsDetailPage />} />
            <Route path="/mall/cart" element={<RequireAuth><CartPage /></RequireAuth>} />
            <Route path="/mall/checkout" element={<RequireAuth><CheckoutPage /></RequireAuth>} />
            <Route path="/mall/orders" element={<RequireAuth><OrdersPage /></RequireAuth>} />
            <Route path="/mall/orders/:orderNo" element={<RequireAuth><OrderDetailPage /></RequireAuth>} />
            <Route path="/mall/refunds" element={<RequireAuth><RefundListPage /></RequireAuth>} />
            <Route path="/mall/evaluations" element={<RequireAuth><EvaluationCenterPage /></RequireAuth>} />
            <Route path="/mall/coupons" element={<RequireAuth><CouponCenterPage /></RequireAuth>} />
            <Route path="/mall/favorites" element={<RequireAuth><FavoritesPage /></RequireAuth>} />
            <Route path="/mall/footprints" element={<RequireAuth><FootprintsPage /></RequireAuth>} />
            <Route path="/mall/chat" element={<RequireAuth><ChatPage /></RequireAuth>} />
            <Route path="/mall/help" element={<HelpCenterPage />} />
            <Route path="/mall/info/:key" element={<SiteInfoPage />} />
          </Route>
        )}
        {hasFeature('mall') && (
          <Route element={<RequireAuth><SellerLayout /></RequireAuth>}>
            <Route path="/mall/seller/shop" element={<ShopManagePage />} />
            <Route path="/mall/seller/goods" element={<GoodsManagePage />} />
            <Route path="/mall/seller/orders" element={<OrdersManagePage />} />
            <Route path="/mall/seller/refunds" element={<RefundManagePage />} />
            <Route path="/mall/seller/evaluations" element={<EvaluationManagePage />} />
            <Route path="/mall/seller/coupons" element={<CouponManagePage />} />
            <Route path="/mall/seller/wallet" element={<WalletPage />} />
            <Route path="/mall/seller/chat" element={<SellerChatPage />} />
          </Route>
        )}
        {hasFeature('mall') && (
          <Route path="/mall/admin/shops" element={<RequireAdmin><ShopReviewPage /></RequireAdmin>} />
        )}
        {hasFeature('mall') && (
          <Route path="/mall/admin/withdrawals" element={<RequireAdmin><WithdrawReviewPage /></RequireAdmin>} />
        )}
        {hasFeature('mall') && (
          <Route path="/mall/admin/coupons" element={<RequireAdmin><CouponAdminPage /></RequireAdmin>} />
        )}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <ThemeToggle />
    </>
  )
}

export default function App() {
  return (
    <Router>
      <RuntimeConfigProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </RuntimeConfigProvider>
    </Router>
  )
}
