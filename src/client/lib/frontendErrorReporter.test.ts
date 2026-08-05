import { describe, expect, it } from 'vitest'
import { buildCurl } from './frontendErrorReporter'

describe('buildCurl', () => {
  it('redacts credentials and truncates large textual form fields', async () => {
    const form = new FormData()
    form.append('password', 'do-not-log')
    form.append('note', 'x'.repeat(1400))

    const result = await buildCurl({
      method: 'post',
      url: 'https://api.example.test/upload?access_token=secret',
      headers: { Authorization: 'Bearer secret' },
      body: form,
    })

    expect(result.curl).toContain('[REDACTED]')
    expect(result.curl).not.toContain('Bearer secret')
    expect(result.curl).not.toContain('do-not-log')
    expect(String((result.body as Record<string, unknown>).note)).toHaveLength(1024)
  })

  it('keeps ordinary JSON bodies reproducible in the curl command', async () => {
    const result = await buildCurl({
      method: 'POST',
      url: '/api/example',
      headers: { 'Content-Type': 'application/json' },
      body: { name: 'example' },
    })

    expect(result.curl).toContain("--data-raw '{\"name\":\"example\"}'")
    expect(result.headers['Content-Type']).toBe('application/json')
  })
})
