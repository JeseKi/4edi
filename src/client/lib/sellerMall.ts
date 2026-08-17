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

export const applyMallShop = async (payload: {
  name: string
  description?: string
  avatar?: string
}): Promise<MallShop> => (await api.post<MallShop>('/mall/seller/shop/apply', payload)).data

export const updateMallShop = async (payload: {
  name?: string
  description?: string
  avatar?: string
}): Promise<MallShop> => (await api.put<MallShop>('/mall/seller/shop', payload)).data

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
  keyword?: string
  page?: number
  page_size?: number
}): Promise<MallPage<MallShop>> =>
  (await api.get<MallPage<MallShop>>('/mall/admin/shops', { params })).data

export const reviewAdminShop = async (
  shopId: number,
  payload: { approved: boolean; reject_reason?: string },
): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/review`, payload)).data

export const closeAdminShop = async (shopId: number): Promise<MallShop> =>
  (await api.post<MallShop>(`/mall/admin/shops/${shopId}/close`)).data

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
