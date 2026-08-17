import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { App, Button, Empty, Input, Modal, Pagination, Rate, Spin, Tabs, Tag } from 'antd'
import {
  appendMallEvaluation,
  createMallEvaluation,
  listMyEvaluations,
  listPendingEvaluations,
} from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import type { MallEvaluation, PendingEvaluation } from '../../lib/types'

function ImageInput({
  value,
  onChange,
  placeholder = '输入图片 URL 后回车添加',
}: {
  value: string[]
  onChange: (images: string[]) => void
  placeholder?: string
}) {
  const [input, setInput] = useState('')
  const add = () => {
    const url = input.trim()
    if (!url) return
    onChange([...value, url])
    setInput('')
  }
  return (
    <div>
      <div className="flex gap-2">
        <Input
          value={input}
          placeholder={placeholder}
          onChange={(e) => setInput(e.target.value)}
          onPressEnter={add}
        />
        <Button onClick={add}>添加</Button>
      </div>
      {value.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {value.map((url, index) => (
            <Tag
              key={`${url}-${index}`}
              closable
              onClose={() => onChange(value.filter((_, i) => i !== index))}
            >
              {url}
            </Tag>
          ))}
        </div>
      )}
    </div>
  )
}

export default function EvaluationCenterPage() {
  const { message } = App.useApp()
  const [searchParams] = useSearchParams()
  const orderNoFilter = searchParams.get('order_no') ?? ''

  const [activeTab, setActiveTab] = useState('pending')
  const [pending, setPending] = useState<PendingEvaluation[]>([])
  const [myEvals, setMyEvals] = useState<MallEvaluation[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  const [target, setTarget] = useState<PendingEvaluation | null>(null)
  const [rating, setRating] = useState(5)
  const [content, setContent] = useState('')
  const [images, setImages] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)

  const [appendTarget, setAppendTarget] = useState<MallEvaluation | null>(null)
  const [appendContent, setAppendContent] = useState('')
  const [appendImages, setAppendImages] = useState<string[]>([])

  const loadPending = useCallback(async () => {
    setLoading(true)
    try {
      const items = await listPendingEvaluations()
      setPending(orderNoFilter ? items.filter((i) => i.order_no === orderNoFilter) : items)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '待评价列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [message, orderNoFilter])

  const loadMine = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listMyEvaluations({ page, page_size: 10 })
      setMyEvals(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '已评价列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, message])

  useEffect(() => {
    if (activeTab === 'pending') loadPending()
    else loadMine()
  }, [activeTab, loadPending, loadMine])

  const openEvaluate = (item: PendingEvaluation) => {
    setTarget(item)
    setRating(5)
    setContent('')
    setImages([])
  }

  const submitEvaluation = async () => {
    if (!target) return
    if (!content.trim()) {
      message.warning('请填写评价内容')
      return
    }
    setSubmitting(true)
    try {
      await createMallEvaluation(target.order_no, {
        order_item_id: target.order_item_id,
        rating,
        content: content.trim(),
        images,
      })
      message.success('评价成功，感谢您的反馈')
      setTarget(null)
      loadPending()
      setActiveTab('mine')
      setPage(1)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '评价提交失败'))
    } finally {
      setSubmitting(false)
    }
  }

  const openAppend = (evaluation: MallEvaluation) => {
    setAppendTarget(evaluation)
    setAppendContent('')
    setAppendImages([])
  }

  const submitAppend = async () => {
    if (!appendTarget) return
    if (!appendContent.trim()) {
      message.warning('请填写追评内容')
      return
    }
    setSubmitting(true)
    try {
      await appendMallEvaluation(appendTarget.id, {
        content: appendContent.trim(),
        images: appendImages,
      })
      message.success('追评成功')
      setAppendTarget(null)
      loadMine()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '追评提交失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        评价中心
      </h3>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          { key: 'pending', label: `待评价（${pending.length}）` },
          { key: 'mine', label: '已评价' },
        ]}
      />

      <Spin spinning={loading}>
        {activeTab === 'pending' ? (
          pending.length === 0 ? (
            <Empty description="暂无待评价商品" style={{ marginTop: 48 }} />
          ) : (
            <div className="space-y-3">
              {pending.map((item) => (
                <div
                  key={`${item.order_no}-${item.order_item_id}`}
                  className="flex items-center gap-3 rounded px-4 py-3"
                  style={{ border: '1px solid #f0f0f0' }}
                >
                  <img
                    src={item.goods_image}
                    alt={item.goods_name}
                    className="rounded"
                    style={{ width: 56, height: 56, objectFit: 'cover', background: '#f7f7f7' }}
                  />
                  <div className="flex-1">
                    <div className="text-sm" style={{ color: '#333' }}>
                      {item.goods_name}
                    </div>
                    <div className="text-xs mt-1" style={{ color: '#999' }}>
                      {item.shop_name} · 订单 {item.order_no} ·{' '}
                      {Object.entries(item.sku_specs)
                        .map(([k, v]) => `${k}:${v}`)
                        .join(' · ')}
                    </div>
                  </div>
                  <Button type="primary" size="small" style={{ background: '#F31947' }} onClick={() => openEvaluate(item)}>
                    去评价
                  </Button>
                </div>
              ))}
            </div>
          )
        ) : myEvals.length === 0 ? (
          <Empty description="暂无评价记录" style={{ marginTop: 48 }} />
        ) : (
          <div className="space-y-3">
            {myEvals.map((evaluation) => (
              <div
                key={evaluation.id}
                className="rounded px-4 py-3"
                style={{ border: '1px solid #f0f0f0' }}
              >
                <div className="flex items-center gap-3">
                  <img
                    src={evaluation.goods_image ?? ''}
                    alt={evaluation.goods_name ?? ''}
                    className="rounded"
                    style={{ width: 56, height: 56, objectFit: 'cover', background: '#f7f7f7' }}
                  />
                  <div className="flex-1">
                    <div className="text-sm" style={{ color: '#333' }}>
                      {evaluation.goods_name}
                    </div>
                    <div className="text-xs mt-1" style={{ color: '#999' }}>
                      订单 {evaluation.order_no} · {evaluation.created_at}
                    </div>
                  </div>
                  <Rate disabled value={evaluation.rating} style={{ fontSize: 14 }} />
                  {evaluation.appended_at ? (
                    <Tag color="green">已追评</Tag>
                  ) : (
                    <Button size="small" onClick={() => openAppend(evaluation)}>
                      追评
                    </Button>
                  )}
                </div>
                <div className="text-sm mt-2" style={{ color: '#555' }}>
                  {evaluation.content}
                </div>
                {evaluation.images.length > 0 && (
                  <div className="mt-2 flex gap-2">
                    {evaluation.images.map((url, index) => (
                      <img
                        key={`${url}-${index}`}
                        src={url}
                        alt="晒图"
                        className="rounded"
                        style={{ width: 64, height: 64, objectFit: 'cover' }}
                      />
                    ))}
                  </div>
                )}
                {evaluation.seller_reply && (
                  <div className="text-xs mt-2 rounded px-3 py-2" style={{ background: '#fafafa', color: '#888' }}>
                    卖家回复：{evaluation.seller_reply}
                  </div>
                )}
                {evaluation.append_content && (
                  <div className="text-sm mt-2" style={{ color: '#777' }}>
                    追评：{evaluation.append_content}
                  </div>
                )}
              </div>
            ))}
            {total > 10 && (
              <div className="flex justify-center mt-4">
                <Pagination current={page} pageSize={10} total={total} onChange={setPage} showSizeChanger={false} />
              </div>
            )}
          </div>
        )}
      </Spin>

      <Modal
        title={`评价商品（${target?.goods_name ?? ''}）`}
        open={target != null}
        onCancel={() => setTarget(null)}
        onOk={submitEvaluation}
        confirmLoading={submitting}
        okText="提交评价"
        cancelText="取消"
        width={460}
      >
        <div className="mt-3 space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-sm" style={{ color: '#555' }}>
              评分
            </span>
            <Rate value={rating} onChange={setRating} />
          </div>
          <Input.TextArea
            placeholder="说说商品的使用感受吧（必填）"
            maxLength={1000}
            rows={4}
            value={content}
            onChange={(e) => setContent(e.target.value)}
          />
          <ImageInput value={images} onChange={setImages} />
        </div>
      </Modal>

      <Modal
        title="追评"
        open={appendTarget != null}
        onCancel={() => setAppendTarget(null)}
        onOk={submitAppend}
        confirmLoading={submitting}
        okText="提交追评"
        cancelText="取消"
        width={460}
      >
        <div className="mt-3 space-y-3">
          <Input.TextArea
            placeholder="补充评价（必填，每次评价仅可追评一次）"
            maxLength={1000}
            rows={4}
            value={appendContent}
            onChange={(e) => setAppendContent(e.target.value)}
          />
          <ImageInput value={appendImages} onChange={setAppendImages} />
        </div>
      </Modal>
    </div>
  )
}
