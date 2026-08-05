import type { AxiosError, AxiosRequestConfig } from 'axios'

const BODY_PREVIEW_BYTES = 1024
const SENSITIVE_KEY = /authorization|cookie|password|passphrase|token|secret|api[-_]?key|code|otp|totp/i

type HeaderRecord = Record<string, string>

interface BodyPreview {
  value: unknown
  truncated: boolean
  isBinary: boolean
}

interface CurlInput {
  method: string
  url: string
  headers?: unknown
  body?: unknown
}

interface RequestCapture {
  method: string
  url: string
  headers: HeaderRecord
  body: unknown
}

interface ResponseCapture {
  status: number | null
  status_text: string | null
  headers: HeaderRecord
  body: unknown
  body_truncated: boolean
  body_is_binary: boolean
}

let installed = false
let nativeFetch: typeof window.fetch | null = null

function isSensitiveKey(key: string): boolean {
  return SENSITIVE_KEY.test(key)
}

function truncateText(value: string): { value: string; truncated: boolean } {
  const bytes = new TextEncoder().encode(value)
  if (bytes.byteLength <= BODY_PREVIEW_BYTES) {
    return { value, truncated: false }
  }
  return {
    value: new TextDecoder().decode(bytes.slice(0, BODY_PREVIEW_BYTES)),
    truncated: true,
  }
}

function sanitizeValue(value: unknown, key?: string): unknown {
  if (key && isSensitiveKey(key)) {
    return '[REDACTED]'
  }
  if (typeof value === 'string') {
    return truncateText(value).value
  }
  if (Array.isArray(value)) {
    return value.map((item) => sanitizeValue(item))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([entryKey, entryValue]) => [entryKey, sanitizeValue(entryValue, entryKey)]),
    )
  }
  return value
}

function shellQuote(value: string): string {
  return `'${value.replace(/'/g, "'\\''")}'`
}

function sanitizeUrl(value: string): string {
  try {
    const base = typeof window === 'undefined' ? 'http://localhost' : window.location.href
    const url = new URL(value, base)
    url.searchParams.forEach((parameterValue, key) => {
      if (isSensitiveKey(key)) {
        url.searchParams.set(key, '[REDACTED]')
      } else {
        url.searchParams.set(key, truncateText(parameterValue).value)
      }
    })
    return url.toString()
  } catch {
    return value
  }
}

function toHeaderRecord(headers: unknown): HeaderRecord {
  if (!headers) {
    return {}
  }
  if (typeof headers === 'string') {
    return headers.split(/\r?\n/).reduce<HeaderRecord>((result, line) => {
      const separator = line.indexOf(':')
      if (separator > 0) {
        const key = line.slice(0, separator).trim()
        result[key] = line.slice(separator + 1).trim()
      }
      return result
    }, {})
  }
  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries())
  }
  if (typeof headers === 'object' && 'toJSON' in headers && typeof headers.toJSON === 'function') {
    return toHeaderRecord(headers.toJSON())
  }
  if (typeof headers === 'object') {
    return Object.fromEntries(
      Object.entries(headers).filter(([, value]) => value !== undefined && value !== null).map(([key, value]) => [key, String(value)]),
    )
  }
  return {}
}

function sanitizeHeaders(headers: unknown): HeaderRecord {
  return Object.fromEntries(
    Object.entries(toHeaderRecord(headers)).map(([key, value]) => [
      key,
      isSensitiveKey(key) ? '[REDACTED]' : truncateText(value).value,
    ]),
  )
}

async function blobPreview(blob: Blob): Promise<BodyPreview> {
  const isBinary = !/^text\/|\b(json|xml|javascript|form-urlencoded)\b/i.test(blob.type)
  const buffer = await blob.slice(0, BODY_PREVIEW_BYTES + 1).arrayBuffer()
  const truncated = blob.size > BODY_PREVIEW_BYTES
  return {
    value: isBinary ? new TextDecoder().decode(buffer.slice(0, BODY_PREVIEW_BYTES)) : truncateText(await blob.slice(0, BODY_PREVIEW_BYTES + 1).text()).value,
    truncated,
    isBinary,
  }
}

async function bodyPreview(value: unknown): Promise<BodyPreview> {
  if (value === undefined || value === null) {
    return { value: null, truncated: false, isBinary: false }
  }
  if (typeof Blob !== 'undefined' && value instanceof Blob) {
    return blobPreview(value)
  }
  if (value instanceof ArrayBuffer) {
    const bytes = new Uint8Array(value.slice(0, BODY_PREVIEW_BYTES + 1))
    return {
      value: new TextDecoder().decode(bytes.slice(0, BODY_PREVIEW_BYTES)),
      truncated: value.byteLength > BODY_PREVIEW_BYTES,
      isBinary: true,
    }
  }
  if (typeof value === 'string') {
    const preview = truncateText(value)
    return { value: preview.value, truncated: preview.truncated, isBinary: false }
  }
  const normalized = sanitizeValue(value)
  const text = JSON.stringify(normalized)
  const preview = truncateText(text)
  return { value: preview.value, truncated: preview.truncated, isBinary: false }
}

async function serializeRequestBody(value: unknown): Promise<{ preview: unknown; curlData?: string }> {
  if (value === undefined || value === null) {
    return { preview: null }
  }
  if (typeof FormData !== 'undefined' && value instanceof FormData) {
    const fields = await Promise.all(Array.from(value.entries()).map(async ([key, fieldValue]) => {
      if (typeof fieldValue === 'string') {
        return [key, sanitizeValue(fieldValue, key)] as const
      }
      const preview = await blobPreview(fieldValue)
      return [key, isSensitiveKey(key) ? '[REDACTED]' : preview.value] as const
    }))
    return {
      preview: Object.fromEntries(fields),
      curlData: fields.map(([key, fieldValue]) => `-F ${shellQuote(`${key}=${String(fieldValue)}`)}`).join(' '),
    }
  }
  const preview = await bodyPreview(value)
  const text = typeof preview.value === 'string' ? preview.value : JSON.stringify(preview.value)
  return { preview: preview.value, curlData: `--data-raw ${shellQuote(text)}` }
}

export async function buildCurl(input: CurlInput): Promise<{ curl: string; headers: HeaderRecord; body: unknown }> {
  const method = input.method.toUpperCase()
  const url = sanitizeUrl(input.url)
  const headers = sanitizeHeaders(input.headers)
  const serializedBody = await serializeRequestBody(input.body)
  const headerArguments = Object.entries(headers).map(([key, value]) => `--header ${shellQuote(`${key}: ${value}`)}`)
  const parts = ['curl', '--request', method, '--url', shellQuote(url), ...headerArguments]
  if (serializedBody.curlData) {
    parts.push(serializedBody.curlData)
  }
  return { curl: parts.join(' '), headers, body: serializedBody.preview }
}

function collectorUrl(): string {
  const apiBase = (import.meta.env.VITE_API_BASE_URL ?? '/api').replace(/\/$/, '')
  const relativeUrl = `${apiBase || '/api'}/frontend-errors`
  return typeof window === 'undefined' ? relativeUrl : new URL(relativeUrl, window.location.href).toString()
}

function isCollectorUrl(url: string): boolean {
  try {
    const base = typeof window === 'undefined' ? 'http://localhost' : window.location.href
    return new URL(url, base).pathname === new URL(collectorUrl(), base).pathname
  } catch {
    return false
  }
}

function resolveRequestUrl(url: string, baseUrl?: string): string {
  if (!baseUrl) {
    return url
  }
  try {
    const pageUrl = typeof window === 'undefined' ? 'http://localhost' : window.location.href
    if (/^https?:\/\//i.test(url)) {
      return url
    }
    const normalizedBase = new URL(baseUrl, pageUrl).toString().replace(/\/$/, '')
    return new URL(`${normalizedBase}/${url.replace(/^\//, '')}`, pageUrl).toString()
  } catch {
    return url
  }
}

async function submitReport(capture: RequestCapture, response: ResponseCapture | null, error?: unknown, transport = 'fetch'): Promise<void> {
  if (!nativeFetch || isCollectorUrl(capture.url)) {
    return
  }
  try {
    const { curl, headers } = await buildCurl(capture)
    const report = {
      timestamp: new Date().toISOString(),
      transport,
      method: capture.method.toUpperCase(),
      url: sanitizeUrl(capture.url),
      curl,
      request_headers: headers,
      response,
      error: error instanceof Error ? error.message : error ? String(error) : null,
      error_code: typeof error === 'object' && error && 'code' in error ? String(error.code) : null,
      page_url: window.location.href,
      user_agent: navigator.userAgent,
    }
    await nativeFetch(collectorUrl(), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(report),
      credentials: 'omit',
      keepalive: true,
    })
  } catch {
    // 上报失败不能影响用户可见的原始请求结果。
  }
}

async function axiosCapture(config?: AxiosRequestConfig): Promise<RequestCapture> {
  const url = config?.url ?? window.location.href
  return {
    method: config?.method ?? 'GET',
    url: resolveRequestUrl(url, config?.baseURL),
    headers: toHeaderRecord(config?.headers),
    body: config?.data,
  }
}

export function reportAxiosError(error: AxiosError | unknown): void {
  const axiosError = error as AxiosError
  void axiosCapture(axiosError.config).then(async (capture) => {
    const body = await bodyPreview(axiosError.response?.data)
    await submitReport(capture, axiosError.response ? {
      status: axiosError.response.status,
      status_text: axiosError.response.statusText,
      headers: sanitizeHeaders(axiosError.response.headers),
      body: sanitizeValue(body.value),
      body_truncated: body.truncated,
      body_is_binary: body.isBinary,
    } : null, error, 'axios')
  }).catch(() => undefined)
}

async function fetchCapture(input: RequestInfo | URL, init?: RequestInit): Promise<RequestCapture> {
  if (input instanceof Request) {
    const clone = input.clone()
    return {
      method: init?.method ?? clone.method,
      url: clone.url,
      headers: { ...toHeaderRecord(clone.headers), ...toHeaderRecord(init?.headers) },
      body: init?.body ?? await clone.blob(),
    }
  }
  return {
    method: init?.method ?? 'GET',
    url: String(input),
    headers: toHeaderRecord(init?.headers),
    body: init?.body,
  }
}

async function fetchResponseCapture(response: Response): Promise<ResponseCapture> {
  const clone = response.clone()
  const reader = clone.body?.getReader()
  let body: BodyPreview
  if (!reader) {
    body = await bodyPreview(await clone.blob())
  } else {
    const previewBytes = new Uint8Array(BODY_PREVIEW_BYTES + 1)
    let offset = 0
    let done = false
    try {
      while (offset < previewBytes.length && !done) {
        const chunk = await reader.read()
        done = chunk.done
        if (!chunk.value) {
          continue
        }
        const remaining = previewBytes.length - offset
        previewBytes.set(chunk.value.slice(0, remaining), offset)
        offset += Math.min(chunk.value.length, remaining)
      }
    } finally {
      await reader.cancel()
    }
    const contentType = response.headers.get('content-type') ?? ''
    const isBinary = !/^text\/|\b(json|xml|javascript|form-urlencoded)\b/i.test(contentType)
    const text = new TextDecoder().decode(previewBytes.slice(0, Math.min(offset, BODY_PREVIEW_BYTES)))
    body = {
      value: text,
      truncated: offset > BODY_PREVIEW_BYTES || !done,
      isBinary,
    }
  }
  return {
    status: response.status,
    status_text: response.statusText,
    headers: sanitizeHeaders(response.headers),
    body: sanitizeValue(body.value),
    body_truncated: body.truncated,
    body_is_binary: body.isBinary,
  }
}

export function installFrontendErrorReporter(): void {
  if (installed || typeof window === 'undefined') {
    return
  }
  installed = true
  nativeFetch = window.fetch.bind(window)

  window.fetch = async (input, init) => {
    const url = input instanceof Request ? input.url : String(input)
    const capturePromise = isCollectorUrl(url) ? null : fetchCapture(input, init)
    try {
      const response = await nativeFetch!(input, init)
      if (!response.ok && capturePromise) {
        void Promise.all([capturePromise, fetchResponseCapture(response)]).then(([capture, responseCapture]) => submitReport(capture, responseCapture))
      }
      return response
    } catch (error) {
      if (capturePromise) {
        void capturePromise.then((capture) => submitReport(capture, null, error))
      }
      throw error
    }
  }

  const metadata = new WeakMap<XMLHttpRequest, RequestCapture>()
  const proto = XMLHttpRequest.prototype
  const originalOpen = proto.open
  const originalSetRequestHeader = proto.setRequestHeader
  const originalSend = proto.send

  const wrappedOpen = function open(this: XMLHttpRequest, method: string, url: string | URL, async?: boolean, username?: string | null, password?: string | null) {
    metadata.set(this, { method, url: String(url), headers: {}, body: null })
    if (async === undefined) {
      return (originalOpen as (method: string, url: string) => void).call(this, method, String(url))
    }
    return originalOpen.call(this, method, String(url), async, username, password)
  }
  proto.open = wrappedOpen as XMLHttpRequest['open']
  proto.setRequestHeader = function setRequestHeader(name: string, value: string) {
    const request = metadata.get(this)
    if (request) {
      request.headers[name] = value
    }
    return originalSetRequestHeader.call(this, name, value)
  }
  proto.send = function send(body?: Document | XMLHttpRequestBodyInit | null) {
    const request = metadata.get(this)
    if (request) {
      request.body = body
      this.addEventListener('loadend', () => {
        if (isCollectorUrl(request.url) || (this.status > 0 && this.status < 400)) {
          return
        }
        void bodyPreview(this.responseType === '' || this.responseType === 'text' ? this.responseText : this.response).then((preview) => submitReport(request, {
          status: this.status || null,
          status_text: this.statusText || null,
          headers: sanitizeHeaders(this.getAllResponseHeaders()),
          body: sanitizeValue(preview.value),
          body_truncated: preview.truncated,
          body_is_binary: preview.isBinary,
        }, this.status === 0 ? new Error('XMLHttpRequest network error') : undefined, 'xhr'))
      }, { once: true })
    }
    return originalSend.call(this, body ?? null)
  }
}
