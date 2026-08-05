import type { AdminUser, UserRole, UserStatus } from '../../../lib/types'
import { resolveApiErrorMessage } from '../../../lib/error'

export function resolveErrorMessage(error: unknown): string {
  return resolveApiErrorMessage(error, '请求失败，请稍后再试。')
}

const allRoleOptions = [
  { value: 'super_admin' as UserRole, label: '超级管理员' },
  { value: 'admin' as UserRole, label: '管理员' },
  { value: 'user' as UserRole, label: '普通用户' },
]

export function isSuperAdmin(role?: UserRole) {
  return role === 'super_admin'
}

export function canManageUser(currentRole: UserRole | undefined, target: AdminUser) {
  return isSuperAdmin(currentRole) || target.role === 'user'
}

export function getRoleOptions(currentRole?: UserRole) {
  return isSuperAdmin(currentRole) ? allRoleOptions : [allRoleOptions[2]]
}

export function getRoleLabel(role: UserRole) {
  if (role === 'super_admin') return '超级管理员'
  if (role === 'admin') return '管理员'
  return '普通用户'
}

export function getRoleTagColor(role: UserRole) {
  if (role === 'super_admin') return 'gold'
  if (role === 'admin') return 'geekblue'
  return 'default'
}

export const statusOptions = [
  { value: 'active' as UserStatus, label: '启用' },
  { value: 'inactive' as UserStatus, label: '停用' },
]
