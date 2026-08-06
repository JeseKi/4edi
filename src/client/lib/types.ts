export interface TokenResponse {
  access_token: string
  token_type: string
  scope: string
}

export interface MessageResponse {
  message: string
}

export interface Notification { id: string; title: string; body_markdown: string; created_at: string; read_at: string | null }
export interface NotificationListResponse { items: Notification[]; total: number; offset: number; limit: number }
export interface NotificationSummary { unread_count: number; items: Notification[] }
export interface NotificationRecipient { id: number; username: string; name: string | null }
export interface AdminNotificationPayload { audience: 'users' | 'active_users'; recipient_user_ids?: number[]; title: string; body_markdown: string }
export interface AdminNotificationPublished { id: string; recipient_count: number; created_at: string }
export interface AdminNotification { id: string; title: string; body_markdown: string; recipient_count: number; created_at: string; updated_at: string }
export interface AdminNotificationListResponse { items: AdminNotification[]; total: number; offset: number; limit: number }

export type FileAssetStatus = 'pending_upload' | 'available' | 'expired' | 'rejected' | 'deletion_pending' | 'deleted' | 'quarantined'

export interface FileAsset {
  id: string
  created_by_user_id: number
  original_filename: string
  size_bytes: number
  status: FileAssetStatus
  scan_status: string
  upload_expires_at: string
  uploaded_at: string | null
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export interface FileUploadIntentPayload {
  filename: string
  size_bytes: number
}

export interface LocalFileUploadTarget {
  kind: 'local'
  method: 'POST'
  url: string
}

export interface S3PostFileUploadTarget {
  kind: 's3_post'
  method: 'POST'
  url: string
  fields: Record<string, string>
}

export interface FileUploadIntent {
  asset: FileAsset
  upload: LocalFileUploadTarget | S3PostFileUploadTarget
}

export interface FileAssetListResponse {
  items: FileAsset[]
  total: number
  offset: number
  limit: number
}

export interface LoginChallengeResponse {
  requires_2fa: true
  challenge_token: string
  challenge_type: 'totp'
}

export type LoginResponse = TokenResponse | LoginChallengeResponse

export type OAuthProviderName = 'GITHUB' | 'GOOGLE'

export interface OAuthProviderInfo {
  provider: OAuthProviderName
  label: string
}

export interface OAuthProvidersResponse {
  providers: OAuthProviderInfo[]
}

export interface OAuthTicketExchangePayload {
  ticket: string
}

export interface OAuthAuthorizeMetadata {
  client_id: string
  client_name: string
  redirect_uri: string
  permissions: OAuthPermission[]
  state: string | null
}

export interface OAuthPermission {
  scope: string
  title: string
  description: string
}

export interface OAuthAuthorizeConfirmPayload {
  response_type: string
  client_id: string
  redirect_uri: string
  scope: string
  state?: string | null
  code_challenge: string
  code_challenge_method: string
  approve: boolean
}

export interface OAuthAuthorizeResult {
  redirect_url: string
}

export interface OAuthDeviceAuthorizationMetadata {
  client_id: string
  client_name: string
  user_code: string
  permissions: OAuthPermission[]
  expires_at: string
}

export interface OAuthDeviceAuthorizationConfirmPayload {
  user_code: string
  approve: boolean
}

export interface OAuthDeviceAuthorizationResult {
  status: 'approved' | 'denied'
}

export interface OAuthClient {
  id: number
  client_id: string
  name: string
  redirect_uris: string[]
  allowed_scopes: string[]
  is_active: boolean
  require_pkce: boolean
  created_at: string
  updated_at: string
}

export interface OAuthClientWithSecret extends OAuthClient {
  client_secret: string
}

export interface OAuthClientCreatePayload {
  name: string
  redirect_uris: string[]
  allowed_scopes: string[]
  is_active: boolean
  require_pkce: boolean
}

export interface OAuthClientUpdatePayload {
  name?: string
  redirect_uris?: string[]
  allowed_scopes?: string[]
  is_active?: boolean
  require_pkce?: boolean
}

export interface AuthTokens {
  accessToken: string
}

export type UserRole = 'user' | 'admin' | 'super_admin'

export type UserStatus = 'active' | 'inactive'

export interface UserProfile {
  id: number
  username: string
  email: string
  phone: string | null
  name: string | null
  role: UserRole
  status: UserStatus
  two_factor_enabled: boolean
  two_factor_confirmed_at: string | null
}

export interface LoginPayload {
  username: string
  password: string
  turnstile_token?: string
}

export interface TwoFactorVerifyPayload {
  challenge_token: string
  code: string
}

export interface TwoFactorSetupStartResponse {
  secret: string
  secret_masked: string
  otpauth_url: string
  setup_token: string
}

export interface TwoFactorSetupConfirmPayload {
  setup_token: string
  code: string
}

export interface TwoFactorDisablePayload {
  password: string
  code: string
}

export interface TwoFactorRegenerateBackupCodesPayload {
  password: string
  code: string
}

export interface BackupCodesResponse extends MessageResponse {
  backup_codes: string[]
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
}

export interface VerificationCodePayload {
  email: string
  turnstile_token?: string
}

export interface RegisterWithCodePayload {
  username: string
  email: string
  password: string
  code: string
  turnstile_token?: string
}

export interface UpdateProfilePayload {
  username?: string | null
  name?: string | null
}

export interface PasswordResetLinkPayload {
  email: string
  turnstile_token?: string
}

export interface PhoneVerificationCodePayload {
  phone: string
  turnstile_token?: string
}

export interface PhoneRegisterWithCodePayload {
  phone: string
  code: string
  password: string
  turnstile_token?: string
}

export interface PhonePasswordResetPayload {
  phone: string
  code: string
  new_password: string
  turnstile_token?: string
}

export interface PasswordResetWithTokenPayload {
  token: string
  new_password: string
}

export interface EmailChangeCodePayload {
  email: string
}

export interface EmailChangeConfirmPayload {
  email: string
  code: string
}

export interface PasswordChangeConfirmPayload {
  token: string
  new_password: string
}

export interface AdminUser {
  id: number
  username: string
  email: string
  name: string | null
  role: UserRole
  status: UserStatus
  scope_overrides: string[] | null
  effective_scopes: string[]
  available_scopes: string[]
  created_at: string
}

export interface AdminUserCreatePayload {
  username: string
  email: string
  name?: string | null
  role?: UserRole
  status?: UserStatus
  password: string
}

export interface AdminUserUpdatePayload {
  username?: string | null
  email?: string | null
  name?: string | null
  role?: UserRole
  status?: UserStatus
  password?: string | null
}

export interface AdminUserBulkUpdatePayload {
  user_ids: number[]
  role?: UserRole
  status?: UserStatus
}

export interface AdminUserBulkDeletePayload {
  user_ids: number[]
}

export interface AdminUserScopesUpdatePayload {
  scopes: string[]
}

export type ScopeCategory = 'normal' | 'sensitive' | 'dangerous'

export interface AdminScope {
  id: number
  scope: string
  title: string
  description: string
  category: ScopeCategory
  created_at: string
  updated_at: string
}

export interface AdminScopeUpdatePayload {
  category: ScopeCategory
}

export type AuditOutcome = 'success' | 'failure'
export type AuditPriority = 'high' | 'low'

export type AuditMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

export interface AdminAuditEvent {
  id: number
  created_at: string
  outcome: AuditOutcome
  priority: AuditPriority
  action: string
  action_label: string | null
  method: AuditMethod | null
  path: string | null
  path_template: string | null
  http_status_code: number | null
  actor_user_id: number | null
  actor_username: string | null
  actor_role: string | null
  actor_identifier: string | null
  resource_type: string | null
  resource_id: string | null
  target_summary: string | null
  request_id: string | null
  client_ip: string | null
  user_agent: string | null
  duration_ms: number | null
  detail: Record<string, unknown>
}

export interface AdminAuditEventQuery {
  page?: number
  page_size?: number
  q?: string
  outcome?: AuditOutcome
  method?: AuditMethod
  actor_user_id?: number
  resource_type?: string
  created_from?: string
  created_to?: string
}

export interface AdminAuditEventListResponse {
  items: AdminAuditEvent[]
  total: number
  page: number
  page_size: number
}

export interface ItemPayload {
  name: string
}

export interface Item {
  id: number
  name: string
}

export type AsyncTaskStatus = 'pending' | 'running' | 'completed' | 'failed'

export type AsyncTaskLogLevel = 'info' | 'warning' | 'error'

export interface AsyncTaskPayload {
  name: string
  total_count: number
  fail_every: number
  delay_ms: number
}

export interface AsyncTaskLog {
  id: number
  sequence: number
  level: AsyncTaskLogLevel
  message: string
  created_at: string
}

export interface AsyncTask {
  id: number
  name: string
  status: AsyncTaskStatus
  total_count: number
  processed_count: number
  success_count: number
  failure_count: number
  progress_percent: number
  fail_every: number
  delay_ms: number
  last_message: string | null
  requested_by_user_id: number | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface AsyncTaskDetail extends AsyncTask {
  logs: AsyncTaskLog[]
}

// ---------------------------------------------------------------------------
// 商城 mall
// ---------------------------------------------------------------------------

export type MallGoodsStatus = 'draft' | 'on' | 'off'
export type MallShopStatus = 'pending' | 'approved' | 'rejected' | 'closed'
export type MallOrderStatus =
  | 'pending_payment'
  | 'paid'
  | 'shipped'
  | 'completed'
  | 'cancelled'
export type MallWithdrawStatus = 'pending' | 'approved' | 'rejected' | 'paid'
export type MallLedgerType = 'sale' | 'withdraw' | 'deposit'
export type MallLedgerStatus = 'frozen' | 'available' | 'withdrawn'
export type MallChatSenderType = 'buyer' | 'seller'

export interface MallPage<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface MallCategory {
  id: number
  parent_id: number | null
  name: string
  sort: number
  icon: string | null
  children?: MallCategory[]
}

export interface MallShopPublic {
  id: number
  name: string
  avatar: string | null
  description: string | null
}

export interface MallShop extends MallShopPublic {
  owner_user_id: number
  status: MallShopStatus
  reject_reason: string | null
  deposit_fen: number
  approved_at: string | null
  created_at: string
}

export interface MallGoods {
  id: number
  shop_id: number
  category_id: number | null
  name: string
  main_image: string
  images: string[]
  detail: string | null
  price_fen: number
  original_price_fen: number | null
  stock: number
  sales: number
  status: MallGoodsStatus
  created_at: string
}

export interface MallGoodsSku {
  id: number
  goods_id: number
  sku_code: string | null
  specs: Record<string, string>
  price_fen: number
  stock: number
}

export interface MallGoodsDetail extends MallGoods {
  shop: MallShopPublic
  skus: MallGoodsSku[]
}

export interface MallCartItem {
  id: number
  goods_id: number
  sku_id: number
  quantity: number
  selected: boolean
  shop_id: number
  shop_name: string
  goods_name: string
  goods_image: string
  sku_specs: Record<string, string>
  price_fen: number
  subtotal_fen: number
  stock: number
  goods_on: boolean
}

export interface MallAddress {
  id: number
  user_id: number
  receiver: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  is_default: boolean
  created_at: string
}

export interface MallOrderItem {
  id: number
  order_id: number
  goods_id: number
  sku_id: number
  goods_name: string
  goods_image: string
  sku_specs: Record<string, string>
  unit_price_fen: number
  quantity: number
  subtotal_fen: number
}

export interface MallOrderLog {
  id: number
  order_id: number
  message: string
  created_at: string
}

export interface MallOrder {
  id: number
  order_no: string
  buyer_id: number
  shop_id: number
  shop_name: string | null
  status: MallOrderStatus
  goods_amount_fen: number
  freight_fen: number
  pay_amount_fen: number
  receiver_name: string
  receiver_phone: string
  receiver_address: string
  remark: string | null
  shipping_company: string | null
  tracking_no: string | null
  shipping_traces: string[] | null
  payment_channel: string | null
  payment_type: string | null
  paid_at: string | null
  shipped_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  cancel_reason: string | null
  created_at: string
  items: MallOrderItem[]
  logs: MallOrderLog[]
}

export interface MallOrderPreviewItem {
  sku_id: number
  goods_id: number
  goods_name: string
  goods_image: string
  sku_specs: Record<string, string>
  unit_price_fen: number
  quantity: number
  subtotal_fen: number
  stock: number
}

export interface MallOrderPreview {
  items: MallOrderPreviewItem[]
  goods_amount_fen: number
  freight_fen: number
  pay_amount_fen: number
}

export interface MallPaymentPrepay {
  id: number
  out_trade_no: string
  order_no: string
  amount_fen: number
  channel: string
  pay_type: string | null
  code_url: string | null
  prepay_id: string | null
  mode: string
}

export interface MallWallet {
  shop_id: number
  available_fen: number
  frozen_fen: number
  deposit_fen: number
  total_fen: number
}

export interface MallWalletLedger {
  id: number
  shop_id: number
  entry_type: MallLedgerType
  status: MallLedgerStatus
  amount_fen: number
  related_no: string | null
  note: string | null
  available_at: string | null
  created_at: string
}

export interface MallWithdraw {
  id: number
  shop_id: number
  withdraw_no: string
  amount_fen: number
  status: MallWithdrawStatus
  account_info: Record<string, string>
  reject_reason: string | null
  handled_at: string | null
  created_at: string
}

export interface MallChatMessage {
  id: number
  shop_id: number
  order_no: string | null
  sender_type: MallChatSenderType
  sender_user_id: number | null
  content: string
  read_at: string | null
  created_at: string
}

export interface MallChatConversation {
  shop_id: number
  shop_name: string
  order_no: string | null
  last_message: string
  last_message_at: string | null
  unread_count: number
}
