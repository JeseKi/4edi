import { describe, expect, it } from 'vitest'

import { sellerAgreementAction, sellerOnboardingStepIndex } from './agreementActions'

describe('sellerAgreementAction', () => {
  it('在线协议在签署前显示确认，签署后只显示电子协议', () => {
    expect(sellerAgreementAction('agreement_generated', 'online_click')).toBe('online_accept')
    expect(sellerAgreementAction('agreement_archived', 'online_click')).toBe('online_view')
    expect(sellerAgreementAction('approved', 'online_click')).toBe('online_view')
    expect(sellerAgreementAction('merchant_signed', 'online_click')).toBeNull()
  })

  it.each(['platform_signed', 'agreement_archived', 'approved'] as const)(
    '历史文件协议在 %s 阶段显示双方签署文件',
    (stage) => {
      expect(sellerAgreementAction(stage, 'uploaded_document')).toBe('legacy_signed_file')
    },
  )

  it('历史未完成协议保留上传入口', () => {
    expect(sellerAgreementAction('agreement_generated', 'uploaded_document')).toBe('legacy_upload')
  })

  it('把新旧数据库阶段归并为四步展示', () => {
    expect(sellerOnboardingStepIndex('qualification_submitted')).toBe(0)
    expect(sellerOnboardingStepIndex('qualification_preapproved')).toBe(1)
    expect(sellerOnboardingStepIndex('agreement_generated')).toBe(2)
    expect(sellerOnboardingStepIndex('merchant_signed')).toBe(2)
    expect(sellerOnboardingStepIndex('platform_signed')).toBe(2)
    expect(sellerOnboardingStepIndex('agreement_archived')).toBe(2)
    expect(sellerOnboardingStepIndex('approved')).toBe(3)
  })
})
