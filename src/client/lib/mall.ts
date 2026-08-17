import api from './api'
import type {
  GoodsEvaluationList,
  MallAddress,
  MallCartItem,
  MallCategory,
  MallChatConversation,
  MallChatMessage,
  MallCouponScope,
  MallCouponTemplate,
  MallEvaluation,
  MallFavorite,
  MallFavoriteTargetType,
  MallFootprint,
  MallGoods,
  MallGoodsDetail,
  MallOrder,
  MallOrderPreview,
  MallOrderStatus,
  MallPage,
  MallPaymentPrepay,
  MallRefund,
  MallRefundType,
  MallShopPublic,
  MallUserCoupon,
  MallUserCouponStatus,
  PendingEvaluation,
} from './types'

// ---------------------------------------------------------------------------
// 分类 / 商品 / 店铺
// ---------------------------------------------------------------------------

export const listMallCategories = async (): Promise<MallCategory[]> =>
  (await api.get<MallCategory[]>('/mall/categories')).data

export interface MallGoodsQuery {
  keyword?: string
  category_id?: number
  shop_id?: number
  sort?: 'default' | 'sales' | 'price_asc' | 'price_desc' | 'new'
  page?: number
  page_size?: number
}

export const searchMallGoods = async (params: MallGoodsQuery): Promise<MallPage<MallGoods>> =>
  (await api.get<MallPage<MallGoods>>('/mall/goods', { params })).data

export const getMallGoodsDetail = async (goodsId: number): Promise<MallGoodsDetail> =>
  (await api.get<MallGoodsDetail>(`/mall/goods/${goodsId}`)).data

export const getMallShopPublic = async (shopId: number): Promise<MallShopPublic> =>
  (await api.get<MallShopPublic>(`/mall/shops/${shopId}`)).data

// ---------------------------------------------------------------------------
// 购物车
// ---------------------------------------------------------------------------

export const addMallCartItem = async (payload: {
  goods_id: number
  sku_id: number
  quantity: number
}): Promise<MallCartItem> => (await api.post<MallCartItem>('/mall/cart/items', payload)).data

export const listMallCart = async (): Promise<MallCartItem[]> =>
  (await api.get<MallCartItem[]>('/mall/cart')).data

export const updateMallCartItem = async (
  itemId: number,
  payload: { quantity?: number; selected?: boolean },
): Promise<MallCartItem> => (await api.patch<MallCartItem>(`/mall/cart/items/${itemId}`, payload)).data

export const deleteMallCartItems = async (itemIds: number[]): Promise<{ deleted: number }> =>
  (await api.delete<{ deleted: number }>('/mall/cart/items', { params: { item_ids: itemIds } })).data

// ---------------------------------------------------------------------------
// 收货地址
// ---------------------------------------------------------------------------

export interface MallAddressPayload {
  receiver: string
  phone: string
  province: string
  city: string
  district: string
  detail: string
  is_default?: boolean
}

export const listMallAddresses = async (): Promise<MallAddress[]> =>
  (await api.get<MallAddress[]>('/mall/addresses')).data

export const createMallAddress = async (payload: MallAddressPayload): Promise<MallAddress> =>
  (await api.post<MallAddress>('/mall/addresses', payload)).data

export const updateMallAddress = async (
  addressId: number,
  payload: MallAddressPayload,
): Promise<MallAddress> =>
  (await api.put<MallAddress>(`/mall/addresses/${addressId}`, payload)).data

export const deleteMallAddress = async (addressId: number): Promise<void> => {
  await api.delete(`/mall/addresses/${addressId}`)
}

// ---------------------------------------------------------------------------
// 订单
// ---------------------------------------------------------------------------

export interface MallOrderItemIn {
  sku_id: number
  quantity: number
}

export const previewMallOrder = async (
  items: MallOrderItemIn[],
  couponId?: number,
): Promise<MallOrderPreview> =>
  (await api.post<MallOrderPreview>('/mall/orders/preview', { items, coupon_id: couponId })).data

export const createMallOrder = async (payload: {
  address_id: number
  items: MallOrderItemIn[]
  cart_item_ids?: number[]
  remark?: string
  coupon_id?: number
}): Promise<MallOrder> => (await api.post<MallOrder>('/mall/orders', payload)).data

export const listMallOrders = async (
  params: { status?: MallOrderStatus; page?: number; page_size?: number } = {},
): Promise<MallPage<MallOrder>> =>
  (await api.get<MallPage<MallOrder>>('/mall/orders', { params })).data

export const getMallOrder = async (orderNo: string): Promise<MallOrder> =>
  (await api.get<MallOrder>(`/mall/orders/${orderNo}`)).data

export const cancelMallOrder = async (orderNo: string): Promise<MallOrder> =>
  (await api.post<MallOrder>(`/mall/orders/${orderNo}/cancel`)).data

export const confirmMallOrder = async (orderNo: string): Promise<MallOrder> =>
  (await api.post<MallOrder>(`/mall/orders/${orderNo}/confirm`)).data

export const getMallOrderTraces = async (orderNo: string): Promise<{ traces: string[] }> =>
  (await api.get<{ traces: string[] }>(`/mall/orders/${orderNo}/traces`)).data

// ---------------------------------------------------------------------------
// 支付
// ---------------------------------------------------------------------------

export const createMallPayment = async (
  orderNo: string,
  payType: 'native' | 'jsapi' = 'native',
): Promise<MallPaymentPrepay> =>
  (await api.post<MallPaymentPrepay>(`/mall/orders/${orderNo}/payment`, { pay_type: payType })).data

export const mockPayMallOrder = async (outTradeNo: string): Promise<{ status: string }> =>
  (await api.post<{ status: string }>(`/mall/payments/${outTradeNo}/mock-pay`)).data

// ---------------------------------------------------------------------------
// 退款 / 售后
// ---------------------------------------------------------------------------

export const createMallRefund = async (payload: {
  order_no: string
  type: MallRefundType
  reason: string
  description?: string
  evidence_images?: string[]
}): Promise<MallRefund> => (await api.post<MallRefund>('/mall/refunds', payload)).data

export const listMyMallRefunds = async (params: {
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallRefund>> =>
  (await api.get<MallPage<MallRefund>>('/mall/refunds', { params })).data

export const getMallRefund = async (refundNo: string): Promise<MallRefund> =>
  (await api.get<MallRefund>(`/mall/refunds/${refundNo}`)).data

export const cancelMallRefund = async (refundNo: string): Promise<MallRefund> =>
  (await api.post<MallRefund>(`/mall/refunds/${refundNo}/cancel`)).data

export const submitMallRefundReturnTracking = async (
  refundNo: string,
  payload: { return_tracking_company: string; return_tracking_no: string },
): Promise<MallRefund> =>
  (await api.post<MallRefund>(`/mall/refunds/${refundNo}/return-tracking`, payload)).data

// ---------------------------------------------------------------------------
// 商品评价 / 晒单
// ---------------------------------------------------------------------------

export const createMallEvaluation = async (
  orderNo: string,
  payload: { order_item_id: number; rating: number; content: string; images?: string[] },
): Promise<MallEvaluation> =>
  (await api.post<MallEvaluation>(`/mall/orders/${orderNo}/evaluations`, payload)).data

export const listPendingEvaluations = async (): Promise<PendingEvaluation[]> =>
  (await api.get<PendingEvaluation[]>('/mall/evaluations/pending')).data

export const listMyEvaluations = async (params: {
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallEvaluation>> =>
  (await api.get<MallPage<MallEvaluation>>('/mall/evaluations/mine', { params })).data

export const appendMallEvaluation = async (
  evaluationId: number,
  payload: { content: string; images?: string[] },
): Promise<MallEvaluation> =>
  (await api.post<MallEvaluation>(`/mall/evaluations/${evaluationId}/append`, payload)).data

export const listGoodsEvaluations = async (
  goodsId: number,
  params: { page?: number; page_size?: number } = {},
): Promise<GoodsEvaluationList> =>
  (await api.get<GoodsEvaluationList>(`/mall/goods/${goodsId}/evaluations`, { params })).data

// ---------------------------------------------------------------------------
// 优惠券
// ---------------------------------------------------------------------------

export const listAvailableCoupons = async (params: {
  scope?: MallCouponScope
  shop_id?: number
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallCouponTemplate>> =>
  (await api.get<MallPage<MallCouponTemplate>>('/mall/coupons', { params })).data

export const receiveCoupon = async (couponId: number): Promise<MallUserCoupon> =>
  (await api.post<MallUserCoupon>(`/mall/coupons/${couponId}/receive`)).data

export const listMyCoupons = async (params: {
  status?: MallUserCouponStatus
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallUserCoupon>> =>
  (await api.get<MallPage<MallUserCoupon>>('/mall/coupons/mine', { params })).data

// ---------------------------------------------------------------------------
// 收藏 / 浏览足迹
// ---------------------------------------------------------------------------

export const addMallFavorite = async (payload: {
  target_type: MallFavoriteTargetType
  target_id: number
}): Promise<MallFavorite> =>
  (await api.post<MallFavorite>('/mall/favorites', payload)).data

export const removeMallFavorite = async (
  targetType: MallFavoriteTargetType,
  targetId: number,
): Promise<{ ok: boolean }> =>
  (
    await api.delete<{ ok: boolean }>('/mall/favorites', {
      params: { target_type: targetType, target_id: targetId },
    })
  ).data

export const listMyFavorites = async (params: {
  target_type?: MallFavoriteTargetType
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallFavorite>> =>
  (await api.get<MallPage<MallFavorite>>('/mall/favorites', { params })).data

export const getMallFavoriteStatus = async (
  targetType: MallFavoriteTargetType,
  targetId: number,
): Promise<{ favorited: boolean }> =>
  (
    await api.get<{ favorited: boolean }>('/mall/favorites/status', {
      params: { target_type: targetType, target_id: targetId },
    })
  ).data

export const recordMallFootprint = async (goodsId: number): Promise<{ ok: boolean }> =>
  (await api.post<{ ok: boolean }>('/mall/footprints', null, { params: { goods_id: goodsId } })).data

export const listMyFootprints = async (params: {
  page?: number
  page_size?: number
} = {}): Promise<MallPage<MallFootprint>> =>
  (await api.get<MallPage<MallFootprint>>('/mall/footprints', { params })).data

// ---------------------------------------------------------------------------
// 客服
// ---------------------------------------------------------------------------

export const sendBuyerChatMessage = async (payload: {
  shop_id: number
  order_no?: string
  content: string
}): Promise<MallChatMessage> => (await api.post<MallChatMessage>('/mall/chat/messages', payload)).data

export const listBuyerChatMessages = async (params: {
  shop_id: number
  order_no?: string
  after_id?: number
}): Promise<MallChatMessage[]> =>
  (await api.get<MallChatMessage[]>('/mall/chat/messages', { params })).data

export const listBuyerChatConversations = async (): Promise<MallChatConversation[]> =>
  (await api.get<MallChatConversation[]>('/mall/chat/conversations')).data
