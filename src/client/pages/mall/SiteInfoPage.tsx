import { Link, useParams } from 'react-router-dom'
import { Button, Card, Descriptions, Result, Typography } from 'antd'
import MarkdownContent from '../../components/common/MarkdownContent'
import { SITE_INFO_PAGES } from './siteInfoContent'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'

export default function SiteInfoPage() {
  const { site } = useRuntimeConfig()
  const { key } = useParams<{ key: string }>()
  const page = key ? SITE_INFO_PAGES[key] : undefined

  if (!page) {
    return (
      <Result
        status="404"
        title="页面不存在"
        subTitle="你访问的内容暂未提供。"
        extra={
          <Link to="/mall">
            <Button type="primary" style={{ background: '#F31947' }}>
              返回商城首页
            </Button>
          </Link>
        }
      />
    )
  }

  return (
    <Card>
      <div className="mb-4">
        <Link to="/mall">返回商城首页</Link>
      </div>
      <Typography.Title level={3} style={{ color: '#222' }}>
        {page.title}
      </Typography.Title>
      <MarkdownContent content={page.html} html />
      {(key === 'about' || key === 'contact' || key === 'service') && (
        <Descriptions
          className="mt-6"
          bordered
          column={1}
          items={[
            { key: 'entity', label: '运营主体', children: site.legalEntityName || '请联系平台确认' },
            { key: 'address', label: '注册地址', children: site.registeredAddress || '请联系平台确认' },
            { key: 'email', label: '客服邮箱', children: site.serviceEmail || '请联系平台确认' },
          ]}
        />
      )}
    </Card>
  )
}
