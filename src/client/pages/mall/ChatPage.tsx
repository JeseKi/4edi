import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { App, Button, Empty, Input, Spin } from 'antd'
import {
  listBuyerChatConversations,
  listBuyerChatMessages,
  sendBuyerChatMessage,
} from '../../lib/mall'
import { resolveApiErrorMessage } from '../../lib/error'
import type { MallChatConversation, MallChatMessage } from '../../lib/types'

export default function ChatPage() {
  const { message } = App.useApp()
  const [searchParams] = useSearchParams()
  const [conversations, setConversations] = useState<MallChatConversation[]>([])
  const [active, setActive] = useState<MallChatConversation | null>(null)
  const [messages, setMessages] = useState<MallChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [loadingConv, setLoadingConv] = useState(true)
  const [loadingMessages, setLoadingMessages] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const shopIdFromUrl = searchParams.get('shop_id') ? Number(searchParams.get('shop_id')) : null
  const orderNoFromUrl = searchParams.get('order_no')

  const loadConversations = useCallback(async () => {
    setLoadingConv(true)
    try {
      setConversations(await listBuyerChatConversations())
    } catch (err) {
      message.error(resolveApiErrorMessage(err, '会话加载失败'))
    } finally {
      setLoadingConv(false)
    }
  }, [message])

  useEffect(() => {
    loadConversations()
  }, [loadConversations])

  const pickConversation = (conv: MallChatConversation) => {
    setActive(conv)
    setInput('')
  }

  const loadMessages = useCallback(
    async (conv: MallChatConversation) => {
      setLoadingMessages(true)
      try {
        const list = await listBuyerChatMessages({
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

  useEffect(() => {
    if (!shopIdFromUrl) return
    loadConversations().then(() => {
      const target: MallChatConversation | undefined = conversations.find(
        (c) => c.shop_id === shopIdFromUrl,
      )
      if (target) {
        pickConversation(target)
      } else {
        setActive({
          shop_id: shopIdFromUrl,
          shop_name: `店铺 ${shopIdFromUrl}`,
          order_no: orderNoFromUrl ?? null,
          last_message: '',
          last_message_at: null,
          unread_count: 0,
        })
      }
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopIdFromUrl])

  const send = async () => {
    const content = input.trim()
    if (!content || !active) return
    setSending(true)
    try {
      await sendBuyerChatMessage({
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
    <div className="flex rounded overflow-hidden bg-white" style={{ height: 560 }}>
      <aside className="w-60 shrink-0 border-r" style={{ borderColor: '#f0f0f0' }}>
        <div className="px-4 py-3 text-sm font-bold" style={{ color: '#333', borderBottom: '1px solid #f0f0f0' }}>
          在线客服
        </div>
        <div className="overflow-y-auto" style={{ height: 500 }}>
          {loadingConv ? (
            <div className="flex justify-center py-10">
              <Spin />
            </div>
          ) : conversations.length === 0 ? (
            <Empty description="暂无会话" image={Empty.PRESENTED_IMAGE_SIMPLE} style={{ marginTop: 60 }} />
          ) : (
            conversations.map((conv) => (
              <button
                key={`${conv.shop_id}-${conv.order_no ?? ''}`}
                type="button"
                onClick={() => pickConversation(conv)}
                className="w-full text-left px-4 py-3 cursor-pointer hover:bg-gray-50"
                style={{
                  background: active?.shop_id === conv.shop_id ? '#fff7f8' : '#fff',
                  borderBottom: '1px solid #f7f7f7',
                }}
              >
                <div className="text-sm font-medium" style={{ color: '#333' }}>
                  {conv.shop_name}
                  {conv.unread_count > 0 && (
                    <span
                      className="ml-2 px-1.5 rounded text-white text-xs"
                      style={{ background: '#F31947' }}
                    >
                      {conv.unread_count}
                    </span>
                  )}
                </div>
                <div className="text-xs mt-1 truncate" style={{ color: '#999' }}>
                  {conv.last_message || (conv.order_no ? `订单 ${conv.order_no}` : '')}
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="flex-1 flex flex-col">
        <div className="px-4 py-3 text-sm font-bold" style={{ color: '#333', borderBottom: '1px solid #f0f0f0' }}>
          {active ? active.shop_name : '选择一个会话开始咨询'}
        </div>
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
                m.sender_type === 'buyer' ? (
                  <div key={m.id} className="flex justify-end">
                    <div
                      className="max-w-[70%] rounded px-3 py-2 text-sm text-white"
                      style={{ background: '#F31947' }}
                    >
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
            placeholder={active ? '请输入消息，Enter 发送' : '请先选择会话'}
            disabled={!active}
            maxLength={500}
          />
          <Button type="primary" onClick={send} loading={sending} disabled={!active} style={{ background: '#F31947' }}>
            发送
          </Button>
        </div>
      </section>
    </div>
  )
}
