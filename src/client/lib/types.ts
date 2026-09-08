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
  user_agreement_version: string
  privacy_policy_version: string
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
  user_agreement_version: string
  privacy_policy_version: string
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
export type ShopOnboardingStage =
  | 'qualification_submitted'
  | 'qualification_preapproved'
  | 'agreement_generated'
  | 'merchant_signed'
  | 'platform_signed'
  | 'agreement_archived'
  | 'approved'
  | 'rejected'
export type ShopAgreementStatus =
  | 'generated'
  | 'merchant_signed'
  | 'platform_signed'
  | 'archived'
  | 'superseded'
export type MallOrderStatus =
  | 'pending_payment'
  | 'paid'
  | 'shipped'
  | 'completed'
  | 'cancelled'
  | 'refunding'
  | 'refunded'
export type MallWithdrawStatus = 'pending' | 'approved' | 'rejected' | 'paid'
export type MallLedgerType = 'sale' | 'withdraw' | 'deposit'
export type MallLedgerStatus = 'frozen' | 'available' | 'withdrawn'
export type MallChatSenderType = 'buyer' | 'seller'
export type MallRefundType = 'refund_only' | 'return_refund'
export type MallRefundStatus =
  | 'pending'
  | 'returning'
  | 'refunding'
  | 'success'
  | 'rejected'
  | 'cancelled'

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
  requires_special_license: boolean
  children?: MallCategory[]
}

export interface MallShopPublic {
  id: number
  name: string
  avatar: string | null
  description: string | null
  legal_entity_name: string | null
  unified_social_credit_code_masked: string | null
  business_address: string | null
  registration_status: string | null
  last_qualification_checked_at: string | null
  qualification_valid_until: string | null
  platform_verified: boolean
}

export interface ShopAgreementSummary {
  id: number
  shop_id: number
  agreement_number: string
  document_version: string
  draft_content_sha256: string
  status: ShopAgreementStatus
  signature_mode: 'online_click' | 'uploaded_document'
  generated_at: string
  merchant_signed_asset_id: string | null
  merchant_signed_by_user_id: number | null
  merchant_signed_account: string | null
  merchant_signed_at: string | null
  platform_signed_asset_id: string | null
  platform_signed_at: string | null
  final_asset_id: string | null
  final_file_sha256: string | null
  archived_at: string | null
}

export interface ShopAgreement extends ShopAgreementSummary {
  content_markdown: string
}

export interface MallShop extends MallShopPublic {
  owner_user_id: number
  real_name: string | null
  identity_number_masked: string | null
  business_license_asset_id: string | null
  identity_front_asset_id: string | null
  identity_back_asset_id: string | null
  legal_entity_name: string | null
  unified_social_credit_code: string | null
  unified_social_credit_code_masked: string | null
  legal_representative: string | null
  registered_address: string | null
  business_address: string | null
  contact_phone: string | null
  business_license_valid_until: string | null
  business_license_long_term: boolean
  special_license_not_required: boolean
  merchant_agreement_version: string | null
  merchant_agreement_asset_id: string | null
  agreement_accepted_at: string | null
  onboarding_stage: ShopOnboardingStage
  current_agreement_id: number | null
  current_agreement: ShopAgreementSummary | null
  qualification_valid_until: string | null
  last_qualification_checked_at: string | null
  registration_status: string | null
  platform_verified: boolean
  qualification_state: 'unverified' | 'valid' | 'expired'
  status: MallShopStatus
  reject_reason: string | null
  deposit_fen: number
  approved_at: string | null
  created_at: string
}

export interface ShopQualificationReview {
  id: number
  shop_id: number
  result: string
  verification_source: string
  checked_at: string
  reviewer_user_id: number
  evidence_asset_id: string
  registration_status: string
  checklist: Record<string, boolean>
  note: string | null
  reject_reason: string | null
  created_at: string
}

export interface ShopAdminDetail {
  shop: MallShop
  qualification_reviews: ShopQualificationReview[]
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
  coupon_id: number | null
  coupon_discount_fen: number
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
  refunded_at: string | null
  created_at: string
  items: MallOrderItem[]
  logs: MallOrderLog[]
}

export interface MallRefund {
  id: number
  refund_no: string
  order_no: string
  shop_id: number
  shop_name: string | null
  buyer_id: number
  type: MallRefundType
  status: MallRefundStatus
  order_status_snapshot: MallOrderStatus | null
  reason: string
  description: string | null
  evidence_images: string[]
  amount_fen: number
  return_tracking_company: string | null
  return_tracking_no: string | null
  return_shipped_at: string | null
  return_received_at: string | null
  channel: string | null
  channel_refund_id: string | null
  refuse_reason: string | null
  decided_at: string | null
  success_at: string | null
  created_at: string
  order: MallOrder | null
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
  coupon_discount_fen: number
  pay_amount_fen: number
}

export type MallCouponType = 'fixed' | 'discount'
export type MallCouponScope = 'platform' | 'shop'
export type MallCouponStatus = 'active' | 'paused' | 'expired'
export type MallUserCouponStatus = 'unused' | 'used' | 'expired'

export interface MallCouponTemplate {
  id: number
  name: string
  type: MallCouponType
  value_fen: number
  discount: number
  min_amount_fen: number
  scope: MallCouponScope
  shop_id: number | null
  shop_name: string | null
  total_count: number
  received_count: number
  per_user_limit: number
  valid_from: string
  valid_until: string
  status: MallCouponStatus
  created_at: string
}

export interface MallUserCoupon {
  id: number
  user_id: number
  coupon_id: number
  status: MallUserCouponStatus
  order_no: string | null
  received_at: string
  used_at: string | null
  expired_at: string | null
  name: string | null
  type: MallCouponType | null
  value_fen: number | null
  discount: number | null
  min_amount_fen: number | null
  scope: MallCouponScope | null
  shop_id: number | null
  shop_name: string | null
  valid_until: string | null
}

export interface MallEvaluation {
  id: number
  order_id: number
  order_no: string | null
  order_item_id: number
  goods_id: number
  goods_name: string | null
  goods_image: string | null
  sku_specs: Record<string, string>
  shop_id: number
  buyer_id: number
  buyer_username: string | null
  rating: number
  content: string
  images: string[]
  seller_reply: string | null
  seller_replied_at: string | null
  append_content: string | null
  append_images: string[]
  appended_at: string | null
  created_at: string
}

export interface MallEvaluationSummary {
  avg_rating: number
  rating_count: number
  good_rate: number
  total: number
}

export interface PendingEvaluation {
  order_no: string
  order_item_id: number
  goods_id: number
  goods_name: string
  goods_image: string
  sku_specs: Record<string, string>
  shop_id: number
  shop_name: string
}

export interface GoodsEvaluationList extends MallPage<MallEvaluation> {
  summary: MallEvaluationSummary
}

export type MallFavoriteTargetType = 'goods' | 'shop'

export interface MallFavorite {
  id: number
  target_type: MallFavoriteTargetType
  target_id: number
  target_name: string | null
  target_image: string | null
  target_price_fen: number | null
  shop_id: number | null
  created_at: string
}

export interface MallFootprint {
  goods_id: number
  goods_name: string | null
  goods_image: string | null
  price_fen: number | null
  shop_id: number
  shop_name: string | null
  viewed_at: string
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
  expires_at: string
}

export interface MallPayment {
  id: number
  out_trade_no: string
  order_no: string
  amount_fen: number
  channel: string
  pay_type: string | null
  status: string
  transaction_id: string | null
  paid_at: string | null
  created_at: string
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

// ---------------------------------------------------------------------------
// 信息发布（分类信息中心）
// ---------------------------------------------------------------------------

export type InfoStatus = 'pending' | 'approved' | 'rejected'

export interface InfoAttributeField {
  key: string
  label: string
  type: 'text' | 'select' | 'textarea'
  options?: string[]
}

export interface InfoCategory {
  key: string
  name: string
  attributes: InfoAttributeField[]
}

export interface InformationPost {
  id: number
  title: string
  category: string
  category_name: string
  price: string | null
  poster_username: string
  view_count: number
  is_top: boolean
  created_at: string
}

export interface InformationPostDetail extends InformationPost {
  content: string
  attributes: Record<string, string> | null
  contact_name: string
  contact_phone: string | null
  approved_at: string | null
}

export interface InformationMinePost extends InformationPostDetail {
  status: InfoStatus
  reject_reason: string | null
  reviewed_by_user_id: number | null
  reviewed_at: string | null
  withdrawn_at: string | null
  withdrawn_reason: string | null
}

export interface InformationAdminPost extends InformationMinePost {
  poster_user_id: number
  publisher_verification_id: number | null
  publisher_real_name: string | null
  publisher_document_number_masked: string | null
  publisher_verification_valid: boolean
}

export type PublisherVerificationStatus = 'pending' | 'approved' | 'rejected'

export interface PublisherVerification {
  id: number
  user_id: number
  username: string
  real_name: string
  document_type: string
  document_number_masked: string
  document_front_asset_id: string
  document_back_asset_id: string | null
  document_valid_until: string | null
  document_long_term: boolean
  status: PublisherVerificationStatus
  submitted_at: string
  reviewer_user_id: number | null
  reviewer_username: string | null
  reviewed_at: string | null
  reject_reason: string | null
  is_currently_valid: boolean
}

export interface InformationPage {
  items: InformationPost[]
  total: number
  page: number
  page_size: number
}
