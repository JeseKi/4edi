import { Link, useParams } from 'react-router-dom'
import { Button, Card, Result, Typography } from 'antd'
import MarkdownContent from '../../components/common/MarkdownContent'
import { SITE_INFO_PAGES } from './siteInfoContent'

export default function SiteInfoPage() {
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
    </Card>
  )
}
