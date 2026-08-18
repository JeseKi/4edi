import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { Card, Layout, Menu, Typography } from 'antd'
import MarkdownContent from '../../components/common/MarkdownContent'
import { HELP_CATEGORIES, findHelpArticle } from './helpContent'

const { Sider, Content } = Layout

export default function HelpCenterPage() {
  const location = useLocation()
  const hashId = location.hash.replace(/^#/, '')

  const [activeId, setActiveId] = useState<string>(() => {
    if (hashId && findHelpArticle(hashId)) return hashId
    return HELP_CATEGORIES[0].articles[0].id
  })

  useEffect(() => {
    if (hashId && findHelpArticle(hashId)) {
      setActiveId(hashId)
      window.scrollTo({ top: 0 })
    }
  }, [hashId])

  const current = useMemo(() => findHelpArticle(activeId), [activeId])

  const menuItems = HELP_CATEGORIES.map((category, index) => ({
    key: `cat-${index}`,
    label: category.title,
    children: category.articles.map((article) => ({
      key: article.id,
      label: article.title,
    })),
  }))

  return (
    <Layout style={{ background: 'transparent' }}>
      <div className="mb-4">
        <Link to="/mall">返回商城首页</Link>
      </div>
      <Layout style={{ background: '#fff', borderRadius: 8, overflow: 'hidden' }}>
        <Sider width={220} style={{ background: '#fff', borderRight: '1px solid #f0f0f0' }}>
          <Menu
            mode="inline"
            selectedKeys={[activeId]}
            defaultOpenKeys={['cat-0']}
            items={menuItems}
            onClick={({ key }) => {
              if (findHelpArticle(key)) setActiveId(key)
            }}
            style={{ borderRight: 0 }}
          />
        </Sider>
        <Content style={{ padding: '24px 28px', minHeight: 480 }}>
          {current ? (
            <>
              <Typography.Title level={3} style={{ color: '#222' }}>
                {current.article.title}
              </Typography.Title>
              <MarkdownContent content={current.article.html} html />
            </>
          ) : (
            <Card>内容不存在</Card>
          )}
        </Content>
      </Layout>
    </Layout>
  )
}
