export function formatFen(fen: number): string {
  return (fen / 100).toFixed(2)
}

export const MALL_ORDER_STATUS_LABELS: Record<string, string> = {
  pending_payment: '待付款',
  paid: '待发货',
  shipped: '待收货',
  completed: '已完成',
  cancelled: '已取消',
}
