import type { ShopOnboardingStage } from '../../../lib/types'

export type SellerAgreementAction = 'draft' | 'signed' | null

export function sellerAgreementAction(
  stage: ShopOnboardingStage,
): SellerAgreementAction {
  if (stage === 'agreement_generated') return 'draft'
  if (stage === 'platform_signed' || stage === 'agreement_archived' || stage === 'approved') {
    return 'signed'
  }
  return null
}
