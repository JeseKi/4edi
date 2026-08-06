import { useCallback, useEffect, useRef, useState } from 'react'
import { App, Button, Empty, Input, Spin } from 'antd'
import {
  listSellerChatConversations,
  listSellerChatMessages,
  sendSellerChatMessage,
} from '../../../lib/sellerMall'
import { resolveApiErrorMessage } from '../../../lib/error'
import type { MallChatConversation, MallChatMessage } from '../../../lib/types'

export default function SellerChatPage() {
  const { message } = App.useApp()
  const [conversations, setConversations] = useState<MallChatConversation[]>([])
  const [active, setActive] = useState<MallChatConversation | null>(null)
  const [messages, setMessages] = useState<MallChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingConv, setLoadingConv] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadConversations = useCallback(async () => {
    setLoadingConv(true)
    try {
      setConversations(await listSellerChatConversations())
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '会话加载失败'))
    } finally {
      setLoadingConv(false)
    }
  }, [message])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  const loadMessages = useCallback(
    async (conv: MallChatConversation) => {
      setLoadingMessages(true)
      try {
        const list = await listSellerChatMessages({
          shop_id: conv.shop_id,
          order_no: conv.order_no ?? undefined,
        })
        setMessages(list)
        loadConversations()
      } catch (err) {
        message.error(resolveApiErrorMessage(err, '消息加载失败'))
      } finally {
        setLoadingMessages(false)
      }
    },
    [loadConversations, message],
  )

  useEffect(() => {
    if (active) loadMessages(active)
  }, [active, loadMessages])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const content = input.trim()
    if (!content || !active) return
    setSending(true)
    try {
      await sendSellerChatMessage({
        shop_id: active.shop_id,
        order_no: active.order_no ?? undefined,
        content,
      })
      setInput('')
      await loadMessages(active)
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '发送失败'))
    } finally {
      setSending(false)
    }
  }

  return (
    <div className="rounded overflow-hidden bg-white" style={{ height: 600 }}>
      <div className="px-4 py-3 text-sm font-bold" style={{ color: '#333', borderBottom: '1px solid #f0f0f0' }}>
        客服消息
      </div>
      <div className="flex" style={{ height: 550 }}>
        <aside className="w-56 shrink-0 border-r overflow-y-auto" style={{ borderColor: '#f0f0f0' }}>
          {loadingConv ? (
            <div className="flex justify-center py-10">
              <Spin />
            </div>
          ) : conversations.length === 0 ? (
            <Empty description="暂无会话" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 60 }} />
          ) : (
            conversations.map((conv) => (
              <button
                key={`${conv.shop_id}-${conv.order_no ?? ''}-${conv.last_message_at ?? ''}`}
                type="button"
                onClick={() => setActive(conv)}
                className="w-full text-left px-4 py-3 cursor-pointer hover:bg-gray-50"
                style={{
                  background: active?.shop_id === conv.shop_id ? '#fff7f8' : '#fff',
                  borderBottom: '1px solid #f7f7f7',
                }}
              >
                <div className="text-sm font-medium" style={{ color: '#333' }}>
                  买家咨询
                  {conv.unread_count > 0 && (
                    <span className="ml-2 px-1.5 rounded text-white text-xs" style={{ background: '#F31947' }}>
                      {conv.unread_count}
                    </span>
                  )}
                </div>
                <div className="text-xs mt-1 truncate" style={{ color: '#999' }}>
                  {conv.order_no ? `订单 ${conv.order_no} · ` : ''}
                  {conv.last_message}
                </div>
              </button>
            ))
          )}
        </aside>

        <section className="flex-1 flex flex-col">
          <div className="flex-1 overflow-y-auto p-4 space-y-3" style={{ background: '#fafafa' }}>
            {!active ? (
              <Empty description="选择左侧会话" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 120 }} />
            ) : loadingMessages ? (
              <div className="flex justify-center py-10">
                <Spin />
              </div>
            ) : (
              <>
                {messages.map((m) =>
                  m.sender_type === 'seller' ? (
                    <div key={m.id} className="flex justify-end">
                      <div className="max-w-[70%] rounded px-3 py-2 text-sm text-white" style={{ background: '#F31947' }}>
                        {m.content}
                      </div>
                    </div>
                  ) : (
                    <div key={m.id} className="flex justify-start">
                      <div className="max-w-[70%] rounded px-3 py-2 text-sm" style={{ background: '#fff', border: '1px solid #eee', color: '#333' }}>
                        {m.content}
                      </div>
                    </div>
                  ),
                )}
                <div ref={bottomRef} />
              </>
            )}
          </div>
          <div className="flex gap-2 p-3 border-t" style={{ borderColor: '#f0f0f0' }}>
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onPressEnter={send}
              placeholder={active ? '请输入回复内容' : '请先选择会话'}
              disabled={!active}
              maxLength={500}
            />
            <Button type="primary" onClick={send} loading={sending} disabled={!active} style={{ background: '#F31947' }}>
              回复
            </Button>
          </div>
        </section>
      </div>
    </div>
  )
}
