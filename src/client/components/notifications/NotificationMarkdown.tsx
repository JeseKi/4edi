import type { ComponentProps } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Components } from 'react-markdown'
import rehypeExternalLinks from 'rehype-external-links'
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
  },
}

export default function NotificationMarkdown({ content }: { content: string }) {
  const { trustedNotificationOrigins } = useRuntimeConfig()
  const trusted = new Set([window.location.origin, ...trustedNotificationOrigins])
  const components: Components = {
    a: ({ href, children, ...props }: ComponentProps<'a'>) => {
      const url = href ? new URL(href, window.location.href) : null
      if (!url || !['http:', 'https:'].includes(url.protocol)) return <span>{children}</span>
      const external = url.origin !== window.location.origin
      return <a {...props} href={url.href} target={external ? '_blank' : undefined} rel={external ? 'noopener noreferrer nofollow' : undefined} onClick={(event) => {
        if (external && !trusted.has(url.origin) && !window.confirm(`该链接并非站内或可信链接：${url.origin}。确定跳转吗？`)) event.preventDefault()
      }}>{children}</a>
    },
    img: ({ alt, ...props }: ComponentProps<'img'>) => <img alt={alt ?? ''} loading="lazy" {...props} />,
    input: (props: ComponentProps<'input'>) => <input {...props} readOnly disabled={props.type === 'checkbox'} />,
    table: ({ children, ...props }: ComponentProps<'table'>) => <div className="notification-table-wrapper"><table {...props}>{children}</table></div>,
  }
  return <div className="notification-markdown"><ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[[rehypeExternalLinks, { rel: ['nofollow', 'noopener', 'noreferrer'], target: '_blank' }], [rehypeSanitize, sanitizeSchema]]} components={components}>{content}</ReactMarkdown></div>
}
