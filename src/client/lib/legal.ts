import api from './api'

export type LegalDocumentType =
  | 'user_agreement'
  | 'privacy_policy'
  | 'merchant_agreement'

export interface LegalDocument {
  document_type: LegalDocumentType
  title: string
  version: string
  effective_at: string
  is_current: boolean
  content_markdown: string
}

export interface LegalAcceptanceStatus {
  user_agreement_version: string
  privacy_policy_version: string
  user_agreement_accepted: boolean
  privacy_policy_accepted: boolean
  all_current_accepted: boolean
}

export const listLegalDocuments = async (): Promise<LegalDocument[]> =>
  (await api.get<LegalDocument[]>('/auth/legal-documents')).data

export const getLegalDocument = async (
  documentType: LegalDocumentType,
  version?: string,
): Promise<LegalDocument> =>
  (
    await api.get<LegalDocument>(`/auth/legal-documents/${documentType}`, {
      params: version ? { version } : undefined,
    })
  ).data

export const getMyLegalAcceptanceStatus = async (): Promise<LegalAcceptanceStatus> =>
  (await api.get<LegalAcceptanceStatus>('/auth/legal-acceptances/me')).data

export const acceptCurrentLegalDocuments = async (payload: {
  user_agreement_version: string
  privacy_policy_version: string
}): Promise<LegalAcceptanceStatus> =>
  (await api.post<LegalAcceptanceStatus>('/auth/legal-acceptances/me', payload)).data
