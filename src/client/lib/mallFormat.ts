export function formatFen(fen: number): string {
  return (fen / 100).toFixed(2)
}

export const MALL_ORDER_STATUS_LABELS: Record<string, string> = {
  pending_payment: '待付款',
  paid: '待发货',
  shipped: '待收货',
  completed: '已完成',
  cancelled: '已取消',
  refunding: '退款中',
  refunded: '已退款',
}

export const MALL_REFUND_STATUS_LABELS: Record<string, string> = {
  pending: '待卖家处理',
  returning: '等待买家寄回',
  refunding: '退款处理中',
  success: '退款成功',
  rejected: '已拒绝',
  cancelled: '已取消',
}

export const MALL_REFUND_TYPE_LABELS: Record<string, string> = {
  refund_only: '仅退款',
  return_refund: '退货退款',
}
