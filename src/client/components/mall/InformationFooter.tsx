import { Link } from 'react-router-dom'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'

const withRef = (to: string) => {
  const hashIndex = to.indexOf('#')
  const hash = hashIndex >= 0 ? to.slice(hashIndex) : ''
  const path = hashIndex >= 0 ? to.slice(0, hashIndex) : to
  const sep = path.includes('?') ? '&' : '?'
  return `${path}${sep}ref=information${hash}`
}

export default function InformationFooter() {
  const { site } = useRuntimeConfig()
  return (
    <footer style={{ color: '#666', background: '#fff' }}>
      <div className="mx-auto px-4" style={{ maxWidth: 1184 }}>
        <div className="flex flex-wrap justify-between gap-y-6 py-8">
          {[
            {
              title: '信息发布',
              items: [
                { text: '信息发布', to: '/mall/information/post' },
                { text: '我的发布', to: '/mall/information/mine' },
                { text: '信息广场', to: '/mall/information' },
                { text: '分类浏览', to: '/mall/information' },
              ],
            },
            {
              title: '投诉与帮助',
              items: [
                { text: '投诉入口', to: '/mall/complaint' },
                { text: '常见问题', to: '/mall/help#faq' },
                { text: '联系客服', to: '/mall/info/service' },
                { text: '商家帮助', to: '/mall/info/seller-help' },
              ],
            },
            {
              title: '关于我们',
              items: [
                { text: '关于我们', to: '/mall/info/about' },
                { text: '联系我们', to: '/mall/info/contact' },
                { text: '用户服务协议', to: '/legal/user-agreement' },
                { text: '隐私政策', to: '/legal/privacy-policy' },
                { text: '商家入驻协议', to: '/legal/merchant-agreement' },
              ],
            },
            {
              title: '热门分类',
              items: [
                { text: '小程序开发', to: '/mall/information?category=mini_program' },
                { text: 'APP开发', to: '/mall/information?category=app' },
                { text: '软件开发', to: '/mall/information?category=software' },
                { text: '网站建设', to: '/mall/information?category=website' },
              ],
            },
          ].map((col) => (
            <div key={col.title} style={{ minWidth: 140 }}>
              <div className="text-sm font-bold mb-3" style={{ color: '#333' }}>
                {col.title}
              </div>
              <ul className="space-y-2">
                {col.items.map((item) => (
                  <li key={item.text} className="text-xs" style={{ color: '#999' }}>
                    <Link to={withRef(item.to)}>{item.text}</Link>
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
          <Link to={withRef('/mall/information/post')}>信息发布</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to={withRef('/mall/complaint')}>投诉入口</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to={withRef('/mall/information?sort=hot')}>热门榜单</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to={withRef('/mall/information?sort=recommended')}>热门推荐</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to="/legal/user-agreement">用户服务协议</Link>
          <span style={{ margin: '0 8px', color: '#ddd' }}>·</span>
          <Link to="/legal/privacy-policy">隐私政策</Link>
        </div>

        <div className="text-center text-xs pb-6" style={{ color: '#999' }}>
          {site.legalEntityName || site.siteName} ·{' '}
          <a
            href="https://beian.miit.gov.cn/"
            target="_blank"
            rel="noopener noreferrer"
            style={{ color: '#999' }}
          >
            {site.icpRecordNumber}
          </a>
          <br />
          Copyright © 2026 {site.siteName}
        </div>
      </div>
    </footer>
  )
}
