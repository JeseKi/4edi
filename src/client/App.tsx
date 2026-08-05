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
        <Route path="/" element={<LandingPage />} />
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
