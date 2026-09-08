import api from './api'
import type {
  MallChatConversation,
  MallChatMessage,
  MallCouponStatus,
  MallCouponTemplate,
  MallCouponType,
  MallEvaluation,
  MallGoods,
  MallGoodsDetail,
  MallGoodsStatus,
  MallOrder,
  MallOrderStatus,
  MallPage,
  MallRefund,
  MallRefundStatus,
  MallShop,
  ShopAgreement,
  ShopAdminDetail,
  MallWallet,
  MallWalletLedger,
  MallWithdraw,
  MallWithdrawStatus,
} from './types'

export interface MallCouponPayload {
  name: string
  type: MallCouponType
  value_fen?: number
  discount?: number
  min_amount_fen?: number
  scope?: 'platform' | 'shop'
  shop_id?: number
  total_count?: number
  per_user_limit?: number
  valid_from: string
  valid_until: string
}

// ---------------------------------------------------------------------------
// 商家：店铺
// ---------------------------------------------------------------------------

export const getMyMallShop = async (): Promise<MallShop> =>
  (await api.get<MallShop>('/mall/seller/shop')).data

export interface MallShopApplicationPayload {
  name: string
  description?: string
  avatar?: string
  real_name: string
  identity_number: string
  business_license_asset_id: string
  identity_front_asset_id: string
  identity_back_asset_id: string
  legal_entity_name: string
  unified_social_credit_code: string
  legal_representative: string
  registered_address: string
  business_address: string
  contact_phone: string
  business_license_valid_until?: string
  business_license_long_term: boolean
  special_license_not_required: true
}

export const applyMallShop = async (payload: MallShopApplicationPayload): Promise<MallShop> =>
  (await api.post<MallShop>('/mall/seller/shop/apply', payload)).data

export const resubmitMallShopQualification = async (
  payload: MallShopApplicationPayload,
): Promise<MallShop> =>
  (await api.post<MallShop>('/mall/seller/shop/qualification/resubmit', payload)).data

export const getMyShopAgreement = async (): Promise<ShopAgreement> =>
  (await api.get<ShopAgreement>('/mall/seller/shop/agreement')).data

export const submitMerchantSignedAgreement = async (payload: {
  agreement_number: string
  document_version: string
  merchant_signed_asset_id: string
  confirmed: boolean
}): Promise<MallShop> =>
  (await api.post<MallShop>('/mall/seller/shop/agreement/merchant-sign', payload)).data

export const acceptMerchantAgreement = async (payload: {
  agreement_number: string
  document_version: string
  draft_content_sha256: string
  confirmed: true
}): Promise<MallShop> =>
  (await api.post<MallShop>('/mall/seller/shop/agreement/accept', payload)).data

export const updateMallShop = async (payload: {
  name?: string
  description?: string
  avatar?: string
}): Promise<MallShop> => (await api.put<MallShop>('/mall/seller/shop', payload)).data

export const reopenAdminShop = async (shopId: number): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/reopen`)).data

// ---------------------------------------------------------------------------
// 商家：商品
// ---------------------------------------------------------------------------

export interface MallSkuPayload {
  sku_code?: string
  specs: Record<string, string>
  price_fen: number
  stock: number
}

export interface MallGoodsPayload {
  category_id?: number | null
  name: string
  main_image: string
  images?: string[]
  detail?: string | null
  original_price_fen?: number | null
  skus: MallSkuPayload[]
}

export const listSellerGoods = async (params: {
  status?: MallGoodsStatus
  keyword?: string
  page?: number
  page_size?: number
}): Promise<MallPage<MallGoods>> =>
  (await api.get<MallPage<MallGoods>>('/mall/seller/goods', { params })).data

export const createSellerGoods = async (payload: MallGoodsPayload): Promise<MallGoods> =>
  (await api.post<MallGoods>('/mall/seller/goods', payload)).data

export const getSellerGoods = async (goodsId: number): Promise<MallGoodsDetail> =>
  (await api.get<MallGoodsDetail>(`/mall/seller/goods/${goodsId}`)).data

export const updateSellerGoods = async (
  goodsId: number,
  payload: Partial<MallGoodsPayload>,
): Promise<MallGoods> => (await api.put<MallGoods>(`/mall/seller/goods/${goodsId}`, payload)).data

export const setSellerGoodsStatus = async (goodsId: number, on: boolean): Promise<MallGoods> =>
  (await api.post<MallGoods>(`/mall/seller/goods/${goodsId}/status`, null, { params: { on } })).data

export const deleteSellerGoods = async (goodsId: number): Promise<void> => {
  await api.delete(`/mall/seller/goods/${goodsId}`)
}

// ---------------------------------------------------------------------------
// 商家：订单
// ---------------------------------------------------------------------------

export const listSellerOrders = async (params: {
  status?: MallOrderStatus
  page?: number
  page_size?: number
}): Promise<MallPage<MallOrder>> =>
  (await api.get<MallPage<MallOrder>>('/mall/seller/orders', { params })).data

export const shipSellerOrder = async (
  orderNo: string,
  payload: { shipping_company: string; tracking_no: string },
): Promise<MallOrder> =>
  (await api.post<MallOrder>(`/mall/seller/orders/${orderNo}/ship`, payload)).data

// ---------------------------------------------------------------------------
// 商家：退款 / 售后
// ---------------------------------------------------------------------------

export const listSellerRefunds = async (params: {
  status?: MallRefundStatus
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallRefund>> =>
  (await api.get<MallPage<MallRefund>>('/mall/seller/refunds', { params })).data

export const getSellerRefund = async (refundNo: string): Promise<MallRefund> =>
  (await api.get<MallRefund>(`/mall/seller/refunds/${refundNo}`)).data

export const agreeSellerRefund = async (refundNo: string): Promise<MallRefund> =>
  (await api.post<MallRefund>(`/mall/seller/refunds/${refundNo}/agree`)).data

export const rejectSellerRefund = async (
  refundNo: string,
  payload: { reason: string },
): Promise<MallRefund> =>
  (await api.post<MallRefund>(`/mall/seller/refunds/${refundNo}/reject`, payload)).data

export const confirmSellerRefundReturn = async (refundNo: string): Promise<MallRefund> =>
  (await api.post<MallRefund>(`/mall/seller/refunds/${refundNo}/confirm-return`)).data

// ---------------------------------------------------------------------------
// 商家：商品评价
// ---------------------------------------------------------------------------

export const listSellerEvaluations = async (params: {
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallEvaluation>> =>
  (await api.get<MallPage<MallEvaluation>>('/mall/seller/evaluations', { params })).data

export const replySellerEvaluation = async (
  evaluationId: number,
  payload: { content: string },
): Promise<MallEvaluation> =>
  (await api.post<MallEvaluation>(`/mall/seller/evaluations/${evaluationId}/reply`, payload)).data

// ---------------------------------------------------------------------------
// 商家：优惠券
// ---------------------------------------------------------------------------

export const listSellerCoupons = async (params: {
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallCouponTemplate>> =>
  (await api.get<MallPage<MallCouponTemplate>>('/mall/seller/coupons', { params })).data

export const createSellerCoupon = async (payload: MallCouponPayload): Promise<MallCouponTemplate> =>
  (await api.post<MallCouponTemplate>('/mall/seller/coupons', payload)).data

export const updateSellerCoupon = async (
  couponId: number,
  payload: Partial<MallCouponPayload>,
): Promise<MallCouponTemplate> =>
  (await api.put<MallCouponTemplate>(`/mall/seller/coupons/${couponId}`, payload)).data

export const setSellerCouponStatus = async (
  couponId: number,
  on: boolean,
): Promise<MallCouponTemplate> =>
  (await api.post<MallCouponTemplate>(`/mall/seller/coupons/${couponId}/status`, null, { params: { on } })).data

// ---------------------------------------------------------------------------
// 管理员：优惠券
// ---------------------------------------------------------------------------

export const listAdminCoupons = async (params: {
  status?: MallCouponStatus
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallCouponTemplate>> =>
  (await api.get<MallPage<MallCouponTemplate>>('/mall/admin/coupons', { params })).data

export const createAdminCoupon = async (payload: MallCouponPayload): Promise<MallCouponTemplate> =>
  (await api.post<MallCouponTemplate>('/mall/admin/coupons', payload)).data

export const updateAdminCoupon = async (
  couponId: number,
  payload: Partial<MallCouponPayload>,
): Promise<MallCouponTemplate> =>
  (await api.put<MallCouponTemplate>(`/mall/admin/coupons/${couponId}`, payload)).data

export const setAdminCouponStatus = async (
  couponId: number,
  on: boolean,
): Promise<MallCouponTemplate> =>
  (await api.post<MallCouponTemplate>(`/mall/admin/coupons/${couponId}/status`, null, { params: { on } })).data

// ---------------------------------------------------------------------------
// 商家：钱包 / 提现
// ---------------------------------------------------------------------------

export const getSellerWallet = async (): Promise<MallWallet> =>
  (await api.get<MallWallet>('/mall/seller/wallet')).data

export const listSellerLedger = async (params: {
  page?: number
  page_size?: number
}): Promise<MallPage<MallWalletLedger>> =>
  (await api.get<MallPage<MallWalletLedger>>('/mall/seller/wallet/ledger', { params })).data

export const requestMallWithdraw = async (payload: {
  amount_fen: number
  account_info: Record<string, string>
}): Promise<MallWithdraw> =>
  (await api.post<MallWithdraw>('/mall/seller/withdrawals', payload)).data

export const listSellerWithdrawals = async (params: {
  page?: number
  page_size?: number
}): Promise<MallPage<MallWithdraw>> =>
  (await api.get<MallPage<MallWithdraw>>('/mall/seller/withdrawals', { params })).data

// ---------------------------------------------------------------------------
// 商家：客服
// ---------------------------------------------------------------------------

export const listSellerChatConversations = async (): Promise<MallChatConversation[]> =>
  (await api.get<MallChatConversation[]>('/mall/seller/chat/conversations')).data

export const listSellerChatMessages = async (params: {
  shop_id: number
  order_no?: string
  after_id?: number
}): Promise<MallChatMessage[]> =>
  (await api.get<MallChatMessage[]>('/mall/seller/chat/messages', { params })).data

export const sendSellerChatMessage = async (payload: {
  shop_id: number
  order_no?: string
  content: string
}): Promise<MallChatMessage> =>
  (await api.post<MallChatMessage>('/mall/seller/chat/messages', payload)).data

// ---------------------------------------------------------------------------
// 管理员
// ---------------------------------------------------------------------------

export const listAdminShops = async (params: {
  status?: MallShop['status']
  qualification_state?: 'expiring_soon' | 'expired'
  keyword?: string
  page?: number
  page_size?: number
}): Promise<MallPage<MallShop>> =>
  (await api.get<MallPage<MallShop>>('/mall/admin/shops', { params })).data

export const reviewAdminShop = async (
  shopId: number,
  payload: {
    approved: boolean
    reject_reason?: string
    evidence_asset_id: string
    registration_status: string
    verification_source: string
    entity_name_matches: boolean
    credit_code_matches: boolean
    legal_representative_matches: boolean
    registration_status_valid: boolean
    registered_address_matches: boolean
    business_scope_matches: boolean
    special_license_scope_allowed: boolean
    note?: string
  },
): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/review`, payload)).data

export const generateAdminShopAgreement = async (shopId: number): Promise<ShopAgreement> =>
  (await api.post<ShopAgreement>(`/mall/admin/shops/${shopId}/agreement/generate`)).data

export const getAdminShopAgreement = async (shopId: number): Promise<ShopAgreement> =>
  (await api.get<ShopAgreement>(`/mall/admin/shops/${shopId}/agreement`)).data

export const submitAdminPlatformSignedAgreement = async (
  shopId: number,
  payload: { platform_signed_asset_id: string; agreement_matches: boolean },
): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/agreement/platform-sign`, payload)).data

export const archiveAdminShopAgreement = async (shopId: number): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/agreement/archive`)).data

export const approveAdminShop = async (shopId: number): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/approve`)).data

export const closeAdminShop = async (shopId: number): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/close`)).data

export const getAdminShopDetail = async (shopId: number): Promise<ShopAdminDetail> =>
  (await api.get<ShopAdminDetail>(`/mall/admin/shops/${shopId}`)).data

export const listAdminWithdrawals = async (params: {
  status?: MallWithdrawStatus
  page?: number
  page_size?: number
}): Promise<MallPage<MallWithdraw>> =>
  (await api.get<MallPage<MallWithdraw>>('/mall/admin/withdrawals', { params })).data

export const handleAdminWithdraw = async (
  withdrawId: number,
  payload: { approved: boolean; reject_reason?: string },
): Promise<MallWithdraw> =>
  (await api.post<MallWithdraw>(`/mall/admin/withdrawals/${withdrawId}/handle`, payload)).data

export const listAdminRefunds = async (params: {
  status?: MallRefundStatus
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallRefund>> =>
  (await api.get<MallPage<MallRefund>>('/mall/admin/refunds', { params })).data

export const handleAdminRefund = async (
  refundId: number,
  payload: { approved: boolean; reject_reason?: string },
): Promise<MallRefund> =>
  (await api.post<MallRefund>(`/mall/admin/refunds/${refundId}/handle`, payload)).data
