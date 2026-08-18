import type { ComponentProps } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import rehypeExternalLinks from 'rehype-external-links'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import type { Options as SanitizeSchema } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import { useRuntimeConfig } from '../../hooks/useRuntimeConfig'

const sanitizeSchema: SanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    a: [...(defaultSchema.attributes?.a ?? []), 'title', 'target', 'rel'],
    img: [...(defaultSchema.attributes?.img ?? []), 'alt', 'title', 'width', 'height', 'loading'],
    input: [...(defaultSchema.attributes?.input ?? []), ['checked', true], ['readOnly', true]],
    p: [...(defaultSchema.attributes?.p ?? []), 'className'],
    ul: [...(defaultSchema.attributes?.ul ?? []), 'className'],
    ol: [...(defaultSchema.attributes?.ol ?? []), 'className'],
    li: [...(defaultSchema.attributes?.li ?? []), 'className'],
    div: [...(defaultSchema.attributes?.div ?? []), 'className'],
    table: [...(defaultSchema.attributes?.table ?? []), 'className'],
  },
}

interface MarkdownContentProps {
  content: string
  /** 内容本身是 HTML 富文本时传 true，经由 sanitize 后安全渲染。 */
  html?: boolean
}

export default function MarkdownContent({ content, html = false }: MarkdownContentProps) {
  const { trustedNotificationOrigins } = useRuntimeConfig()
  const trusted = new Set([window.location.origin, ...trustedNotificationOrigins])
  const components: Components = {
    a: ({ href, children, ...props }: ComponentProps<'a'>) => {
      const url = href ? new URL(href, window.location.href) : null
      if (!url || !['http:', 'https:'].includes(url.protocol)) return <span>{children}</span>
      const external = url.origin !== window.location.origin
      return (
        <a
          {...props}
          href={url.href}
          target={external ? '_blank' : undefined}
          rel={external ? 'noopener noreferrer nofollow' : undefined}
          onClick={(event) => {
            if (external && !trusted.has(url.origin) && !window.confirm(`该链接并非站内或可信链接：${url.origin}。确定跳转吗？`))
              event.preventDefault()
          }}
        >
          {children}
        </a>
      )
    },
    img: ({ alt, ...props }: ComponentProps<'img'>) => <img alt={alt ?? ''} loading="lazy" {...props} />,
    input: (props: ComponentProps<'input'>) => <input {...props} readOnly disabled={props.type === 'checkbox'} />,
    table: ({ children, ...props }: ComponentProps<'table'>) => (
      <div className="markdown-table-wrapper">
        <table {...props}>{children}</table>
      </div>
    ),
  }

  return (
    <div className="notification-markdown">
      <ReactMarkdown
        remarkPlugins={html ? [remarkGfm] : [remarkGfm]}
        rehypePlugins={
          html
            ? [
                rehypeRaw,
                [rehypeExternalLinks, { rel: ['nofollow', 'noopener', 'noreferrer'], target: '_blank' }],
                [rehypeSanitize, sanitizeSchema],
              ]
            : [
                [rehypeExternalLinks, { rel: ['nofollow', 'noopener', 'noreferrer'], target: '_blank' }],
                [rehypeSanitize, sanitizeSchema],
              ]
        }
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
