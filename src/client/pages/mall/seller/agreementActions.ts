import type { ShopAgreementSummary, ShopOnboardingStage } from '../../../lib/types'

export type SellerAgreementAction =
  | 'online_accept'
  | 'online_view'
  | 'legacy_upload'
  | 'legacy_signed_file'
  | null

export function sellerOnboardingStepIndex(stage: ShopOnboardingStage): number {
  if (stage === 'qualification_submitted') return 0
  if (stage === 'qualification_preapproved' || stage === 'rejected') return 1
  if (
    stage === 'agreement_generated'
    || stage === 'merchant_signed'
    || stage === 'platform_signed'
    || stage === 'agreement_archived'
  ) return 2
  return 3
}

export function sellerAgreementAction(
  stage: ShopOnboardingStage,
  signatureMode: ShopAgreementSummary['signature_mode'],
): SellerAgreementAction {
  if (signatureMode === 'online_click') {
    if (stage === 'agreement_generated') return 'online_accept'
    if (stage === 'agreement_archived' || stage === 'approved') return 'online_view'
    return null
  }
  if (stage === 'agreement_generated') return 'legacy_upload'
  if (stage === 'platform_signed' || stage === 'agreement_archived' || stage === 'approved') {
    return 'legacy_signed_file'
  }
  return null
}
