import { describe, expect, it } from 'vitest'

import { sellerAgreementAction } from './agreementActions'

describe('sellerAgreementAction', () => {
  it('仅在等待商家签署时显示协议定稿', () => {
    expect(sellerAgreementAction('agreement_generated')).toBe('draft')
    expect(sellerAgreementAction('merchant_signed')).toBeNull()
  })

  it.each(['platform_signed', 'agreement_archived', 'approved'] as const)(
    '%s 阶段查看双方签署协议',
    (stage) => {
      expect(sellerAgreementAction(stage)).toBe('signed')
    },
  )
})
