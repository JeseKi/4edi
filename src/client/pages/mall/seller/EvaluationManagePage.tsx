import { useCallback, useEffect, useState } from 'react'
import { App, Button, Empty, Input, Modal, Pagination, Rate, Spin } from 'antd'
import { listSellerEvaluations, replySellerEvaluation } from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { MallEvaluation } from '../../../lib/types'

export default function EvaluationManagePage() {
  const { message } = App.useApp()
  const [items, setItems] = useState<MallEvaluation[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)
  const [replyTarget, setReplyTarget] = useState<MallEvaluation | null>(null)
  const [replyContent, setReplyContent] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await listSellerEvaluations({ page, page_size: 10 })
      setItems(result.items)
      setTotal(result.total)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '评价列表加载失败'))
    } finally {
      setLoading(false)
    }
  }, [page, message])

  useEffect(() => {
    load()
  }, [load])

  const openReply = (evaluation: MallEvaluation) => {
    setReplyTarget(evaluation)
    setReplyContent(evaluation.seller_reply ?? '')
  }

  const submitReply = async () => {
    if (!replyTarget) return
    if (!replyContent.trim()) {
      message.warning('请填写回复内容')
      return
    }
    setSubmitting(true)
    try {
      await replySellerEvaluation(replyTarget.id, { content: replyContent.trim() })
      message.success('回复成功')
      setReplyTarget(null)
      load()
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '回复失败'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded bg-white" style={{ padding: '16px 20px' }}>
      <h3 className="text-base font-bold mb-3" style={{ color: '#333' }}>
        评价管理
      </h3>

      <Spin spinning={loading}>
        {items.length === 0 ? (
          <Empty description="暂无评价" style={{ marginTop: 48 }} />
        ) : (
          <div className="space-y-3">
            {items.map((evaluation) => (
              <div key={evaluation.id} className="rounded px-4 py-3" style={{ border: '1px solid #f0f0f0' }}>
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
                      {evaluation.buyer_username ?? `用户 ${evaluation.buyer_id}`} · 订单{' '}
                      {evaluation.order_no} · {evaluation.created_at}
                    </div>
                  </div>
                  <Rate disabled value={evaluation.rating} style={{ fontSize: 14 }} />
                  <Button
                    size="small"
                    type={evaluation.seller_reply ? 'default' : 'primary'}
                    style={evaluation.seller_reply ? undefined : { background: '#F31947' }}
                    onClick={() => openReply(evaluation)}
                  >
                    {evaluation.seller_reply ? '修改回复' : '回复'}
                  </Button>
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
                  <div className="text-xs mt-2 rounded px-3 py-2" style={{ background: '#fff7f8', color: '#F31947' }}>
                    我的回复：{evaluation.seller_reply}
                  </div>
                )}
                {evaluation.append_content && (
                  <div className="text-sm mt-2" style={{ color: '#777' }}>
                    买家追评：{evaluation.append_content}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Spin>

      {total > 10 && (
        <div className="flex justify-center mt-4">
          <Pagination current={page} pageSize={10} total={total} onChange={setPage} showSizeChanger={false} />
        </div>
      )}

      <Modal
        title="回复评价"
        open={replyTarget != null}
        onCancel={() => setReplyTarget(null)}
        onOk={submitReply}
        confirmLoading={submitting}
        okText="提交回复"
        cancelText="取消"
        width={460}
      >
        <div className="mt-3">
          <div className="text-sm mb-2" style={{ color: '#999' }}>
            买家评价：{replyTarget?.content}
          </div>
          <Input.TextArea
            placeholder="回复内容（必填）"
            maxLength={500}
            rows={4}
            value={replyContent}
            onChange={(e) => setReplyContent(e.target.value)}
          />
        </div>
      </Modal>
    </div>
  )
}
