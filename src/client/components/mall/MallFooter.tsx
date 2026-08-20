import { Link } from 'react-router-dom'

const MALL_PRIMARY = '#F31947'

const withRef = (to: string) => {
  const hashIndex = to.indexOf('#')
  const hash = hashIndex >= 0 ? to.slice(hashIndex) : ''
  const path = hashIndex >= 0 ? to.slice(0, hashIndex) : to
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}ref=mall${hash}`
}

export default function MallFooter() {
  return (
    <footer style={{ color: '#666', background: '#fff' }}>
      <div className="mx-auto px-4" style={{ maxWidth: 1184 }}>
        <div
          className="flex flex-wrap justify-around gap-y-4 py-8"
          style={{ borderBottom: '1px solid #f5f5f5' }}
        >
          {[
            { icon: '多', text: '品类齐全，轻松购物' },
            { icon: '快', text: '多仓直发，极速配送' },
            { icon: '好', text: '正品行货，精致服务' },
            { icon: '省', text: '天天低价，畅选无忧' },
          ].map((item) => (
            <div key={item.icon} className="flex items-center gap-3">
              <span
                className="flex items-center justify-center rounded-full text-sm font-medium"
                style={{
                  width: 40,
                  height: 40,
                  border: `1px solid ${MALL_PRIMARY}`,
                  color: MALL_PRIMARY,
                }}
              >
                {item.icon}
              </span>
              <span className="text-sm" style={{ color: '#333' }}>
                {item.text}
              </span>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap justify-between gap-y-6 py-8">
          {[
            {
              title: '购物指南',
              items: [
                { text: '购物流程', id: 'shopping-process' },
                { text: '会员介绍', id: 'member-intro' },
                { text: '生活旅行', id: 'life-travel' },
                { text: '常见问题', id: 'faq' },
              ],
            },
            {
              title: '配送方式',
              items: [
                { text: '上门自提', id: 'self-pickup' },
                { text: '配送查询', id: 'delivery-query' },
                { text: '收取标准', id: 'shipping-fee' },
                { text: '物流规则', id: 'logistics-rule' },
              ],
            },
            {
              title: '支付方式',
              items: [
                { text: '在线支付', id: 'online-pay' },
                { text: '公司转账', id: 'company-transfer' },
                { text: '余额支付', id: 'balance-pay' },
                { text: '积分支付', id: 'points-pay' },
              ],
            },
            {
              title: '售后服务',
              items: [
                { text: '售后政策', id: 'after-sale-policy' },
                { text: '退款说明', id: 'refund-desc' },
                { text: '返修/退货', id: 'repair-return' },
                { text: '取消订单', id: 'cancel-order' },
              ],
            },
          ].map((col) => (
            <div key={col.title} style={{ minWidth: 140 }}>
              <div className="text-sm font-bold mb-3" style={{ color: '#333' }}>
                {col.title}
              </div>
              <ul className="space-y-2">
                {col.items.map((item) => (
                  <li key={item.id} className="text-xs" style={{ color: '#999' }}>
                    <Link to={withRef(`/mall/help#${item.id}`)}>{item.text}</Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div
          className="text-center text-sm py-4"
          style={{ color: '#666', borderTop: '1px solid #f5f5f5' }}
        >
          <Link to={withRef('/mall/info/about')}>关于我们</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to={withRef('/mall/info/contact')}>联系我们</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to={withRef('/mall/info/service')}>联系客服</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to={withRef('/mall/info/seller-help')}>商家帮助</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to={withRef('/mall/info/privacy')}>隐私政策</Link>
        </div>

        <div className="text-center text-xs pb-6" style={{ color: '#999' }}>
          沐泽商城 ·{' '}
          <a
            href="https://beian.miit.gov.cn/"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#999' }}
          >
            浙ICP备2026035190号-1
          </a>
          <br />
          Copyright © 2026 沐泽健康
        </div>
      </div>
    </footer>
  )
}
