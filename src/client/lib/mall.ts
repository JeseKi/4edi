import api from './api'
import type {
  MallAddress,
  MallCartItem,
  MallCategory,
  MallChatConversation,
  MallChatMessage,
  MallGoods,
  MallGoodsDetail,
  MallOrder,
  MallOrderPreview,
  MallOrderStatus,
  MallPage,
  MallPaymentPrepay,
  MallShopPublic,
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

export const previewMallOrder = async (items: MallOrderItemIn[]): Promise<MallOrderPreview> =>
  (await api.post<MallOrderPreview>('/mall/orders/preview', { items })).data

export const createMallOrder = async (payload: {
  address_id: number
  items: MallOrderItemIn[]
  cart_item_ids?: number[]
  remark?: string
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
