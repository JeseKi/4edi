import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { Button, Empty, Pagination, Segmented, Spin, Tag } from 'antd'
import { ArrowRightOutlined, FireOutlined, EyeOutlined, SendOutlined, UserOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import { useAuth } from '../../../hooks/useAuth'
import {
  listInformation,
  listInformationCategories,
  type InfoSort,
} from '../../../lib/information'
import type { InfoCategory, InformationPost } from '../../../lib/types'

const MALL_PRIMARY = '#F31947'

const SORTS: { key: InfoSort; label: string }[] = [
  { key: 'latest', label: '最新' },
  { key: 'hot', label: '最热' },
  { key: 'recommended', label: '推荐' },
]

function formatDate(value: string): string {
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}

export default function InformationCenterPage() {
  const { isAuthenticated } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const category = searchParams.get('category') ?? ''
  const keyword = searchParams.get('keyword') ?? ''
  const urlSort = searchParams.get('sort')
  const [sort, setSort] = useState<InfoSort>(
    urlSort === 'hot' || urlSort === 'recommended' ? urlSort : 'latest',
  )
  const [page, setPage] = useState(1)
  const [pageSize] = useState(12)
  const [categories, setCategories] = useState<InfoCategory[]>([])
  const [items, setItems] = useState<InformationPost[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [recommended, setRecommended] = useState<InformationPost[]>([])

  useEffect(() => {
    listInformationCategories()
      .then(setCategories)
      .catch(() => {
        // 分类加载失败不阻塞信息中心
      })
  }, [])

  useEffect(() => {
    listInformation({ sort: 'recommended', page: 1, page_size: 5 })
      .then((result) => setRecommended(result.items))
      .catch(() => {
        // 平台推荐加载失败不阻塞
      })
  }, [])

  const setCategory = (key: string) => {
    const next = new URLSearchParams(searchParams)
    if (key) next.set('category', key)
    else next.delete('category')
    setSearchParams(next)
    setPage(1)
  }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listInformation({
        category: category || undefined,
        keyword: keyword || undefined,
        sort,
        page,
        page_size: pageSize,
      })
      setItems(result.items)
      setTotal(result.total)
    } finally {
      setLoading(false)
    }
  }, [category, keyword, sort, page, pageSize])

  useEffect(() => {
    load()
  }, [load])

  const categoryTabs = useMemo(
    () => [
      { key: '', label: '全部' },
      ...categories.map((c) => ({ key: c.key, label: c.name })),
    ],
    [categories],
  )

  const goPost = () => {
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/mall/information/post' } })
      return
    }
    navigate('/mall/information/post')
  }

  return (
    <div className="space-y-4">
      {/* 顶部横幅 */}
      <div
        className="rounded-lg text-white px-6 py-8"
        style={{ background: `linear-gradient(120deg, ${MALL_PRIMARY}, #ff7a45)` }}
      >
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold mb-1">沐泽 · 分类信息中心</h1>
            <p className="text-sm opacity-90">
              小程序 / APP / 软件 / 网站建设 —— 优质服务商信息都在这里
            </p>
          </div>
          <Button
            type="primary"
            size="large"
            icon={<SendOutlined />}
            onClick={goPost}
            style={{ background: '#fff', color: MALL_PRIMARY, border: 'none' }}
          >
            发布信息
          </Button>
        </div>
      </div>

      {/* 信息发布快速上手 */}
      <div className="rounded-lg bg-white px-5 py-4 flex flex-wrap gap-x-8 gap-y-2 text-sm">
        <span className="font-bold" style={{ color: MALL_PRIMARY }}>
          信息发布快速上手
        </span>
        {['登录账号', '选择分类并填写信息', '等待平台审核', '审核通过后公开展示'].map(
          (step, index) => (
            <span key={step} className="flex items-center gap-1" style={{ color: '#666' }}>
              <span
                className="inline-flex items-center justify-center rounded-full text-xs"
                style={{ width: 18, height: 18, background: '#fff1f0', color: MALL_PRIMARY }}
              >
                {index + 1}
              </span>
              {step}
              {index < 3 && <ArrowRightOutlined style={{ color: '#ddd', marginLeft: 8 }} />}
            </span>
          ),
        )}
      </div>

      {/* 分类 + 排序 */}
      <div className="rounded-lg bg-white px-5 py-3 flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-1">
          {categoryTabs.map((tab) => (
            <button
              key={tab.key || 'all'}
              type="button"
              onClick={() => setCategory(tab.key)}
              className={`px-3 py-1 rounded text-sm ${
                category === tab.key
                  ? 'text-white font-medium'
                  : 'hover:bg-gray-50'
              }`}
              style={category === tab.key ? { background: MALL_PRIMARY } : { color: '#555' }}
            >
              {tab.label}
            </button>
          ))}
          <div className="ml-auto">
            <Segmented
              size="small"
              options={SORTS.map((s) => ({ label: s.label, value: s.key }))}
              value={sort}
              onChange={(value) => {
                setSort(value as InfoSort)
                const next = new URLSearchParams(searchParams)
                next.set('sort', value as string)
                setSearchParams(next)
                setPage(1)
              }}
            />
          </div>
        </div>
        {keyword && (
          <div className="text-sm" style={{ color: '#888' }}>
            关键词「{keyword}」的搜索结果，共 {total} 条
          </div>
        )}
      </div>

      {/* 列表 + 平台推荐 */}
      <div className="flex gap-4 items-start">
        <div className="flex-1 min-w-0">
          {loading ? (
            <div className="flex justify-center py-16">
              <Spin size="large" />
            </div>
          ) : items.length === 0 ? (
            <div className="rounded-lg bg-white py-16">
              <Empty description="暂无已通过审核的信息" />
            </div>
          ) : (
            <div className="space-y-3">
              {items.map((item) => (
                <Link
                  key={item.id}
                  to={`/mall/information/${item.id}`}
                  className="block rounded-lg bg-white px-5 py-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        {item.is_top && (
                          <Tag color="volcano" style={{ marginInlineEnd: 0 }}>
                            置顶
                          </Tag>
                        )}
                        <span className="font-medium" style={{ color: '#222' }}>
                          {item.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-4 text-xs mt-1" style={{ color: '#999' }}>
                        <span>{item.category_name}</span>
                        <span>
                          <UserOutlined style={{ marginRight: 4 }} />
                          {item.poster_username}
                        </span>
                        <span>{formatDate(item.created_at)}</span>
                        <span>
                          <EyeOutlined style={{ marginRight: 4 }} />
                          {item.view_count}
                        </span>
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      <div className="text-sm mb-1" style={{ color: MALL_PRIMARY }}>
                        {item.price || '面议'}
                      </div>
                      <span className="text-xs" style={{ color: MALL_PRIMARY }}>
                        查看详情 <ArrowRightOutlined />
                      </span>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}

          {total > pageSize && (
            <div className="flex justify-center mt-4">
              <Pagination
                current={page}
                pageSize={pageSize}
                total={total}
                onChange={setPage}
                showSizeChanger={false}
              />
            </div>
          )}
        </div>

        {/* 平台推荐侧栏 */}
        <div className="hidden lg:block w-64 shrink-0">
          <div className="rounded-lg bg-white p-4">
            <div className="flex items-center gap-2 mb-3">
              <FireOutlined style={{ color: MALL_PRIMARY }} />
              <span className="font-bold" style={{ color: '#333' }}>
                平台推荐
              </span>
            </div>
            {recommended.length === 0 ? (
              <div className="text-xs" style={{ color: '#bbb' }}>
                暂无推荐
              </div>
            ) : (
              <div className="space-y-3">
                {recommended.map((item) => (
                  <Link
                    key={item.id}
                    to={`/mall/information/${item.id}`}
                    className="block text-sm hover:opacity-80"
                    style={{ color: '#555' }}
                  >
                    <div className="line-clamp-2">{item.title}</div>
                    <div className="text-xs mt-1" style={{ color: '#bbb' }}>
                      {item.category_name} · {formatDate(item.created_at)}
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
