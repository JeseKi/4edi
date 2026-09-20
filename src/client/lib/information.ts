import api from './api'
import type {
  InfoCategory,
  InfoStatus,
  InformationAdminPost,
  InformationMinePost,
  InformationPage,
  InformationPostDetail,
  PublisherVerification,
  PublisherVerificationEvidence,
  PublisherVerificationStatus,
} from './types'

// ---------------------------------------------------------------------------
// 分类信息发布
// ---------------------------------------------------------------------------

export type InfoSort = 'latest' | 'hot' | 'recommended'

export type InfoCategoryKey =
  | 'mini_program'
  | 'app'
  | 'software'
  | 'website'

export interface InformationQuery {
  category?: string
  keyword?: string
  sort?: InfoSort
  page?: number
  page_size?: number
}

export const listInformationCategories = async (): Promise<InfoCategory[]> =>
  (await api.get<InfoCategory[]>('/information/categories')).data

export const listInformation = async (params: InformationQuery): Promise<InformationPage> =>
  (await api.get<InformationPage>('/information', { params })).data

export const getInformationDetail = async (postId: number): Promise<InformationPostDetail> =>
  (await api.get<InformationPostDetail>(`/information/${postId}`)).data

export interface InformationCreatePayload {
  category: string
  title: string
  price?: string
  contact_name: string
  contact_phone: string
  content: string
  attributes?: Record<string, string>
}

export const createInformation = async (payload: InformationCreatePayload): Promise<InformationMinePost> =>
  (await api.post<InformationMinePost>('/information', payload)).data

export const listMyInformation = async (): Promise<InformationMinePost[]> =>
  (await api.get<InformationMinePost[]>('/information/mine')).data

export const deleteInformation = async (postId: number): Promise<{ deleted: boolean }> =>
  (await api.delete<{ deleted: boolean }>(`/information/${postId}`)).data

export const getInformationContact = async (postId: number): Promise<{
  contact_name: string
  contact_phone: string
}> => (await api.get(`/information/${postId}/contact`)).data

export const listMyPublisherVerifications = async (): Promise<PublisherVerification[]> =>
  (await api.get<PublisherVerification[]>('/information/verification/me')).data

export const submitPublisherVerification = async (payload: {
  real_name: string
  document_type: string
  document_number: string
  document_front_asset_id: string
  document_back_asset_id?: string
  document_valid_until?: string
  document_long_term: boolean
}): Promise<PublisherVerification> =>
  (await api.post<PublisherVerification>('/information/verification', payload)).data

// ---------------------------------------------------------------------------
// 管理员：信息审核
// ---------------------------------------------------------------------------

export interface AdminInformationQuery {
  status?: InfoStatus
  keyword?: string
  page?: number
  page_size?: number
}

export interface AdminInformationPage {
  items: InformationAdminPost[]
  total: number
  page: number
  page_size: number
}

export const adminListInformation = async (
  params: AdminInformationQuery,
): Promise<AdminInformationPage> =>
  (await api.get<AdminInformationPage>('/information/admin/posts', { params })).data

export const adminReviewInformation = async (
  postId: number,
  payload: { approved: boolean; reject_reason?: string },
): Promise<InformationAdminPost> =>
  (
    await api.post<InformationAdminPost>(
      `/information/admin/posts/${postId}/review`,
      payload,
    )
  ).data

export const adminToggleInformationTop = async (
  postId: number,
  on: boolean,
): Promise<InformationAdminPost> =>
  (
    await api.post<InformationAdminPost>(
      `/information/admin/posts/${postId}/top`,
      null,
      { params: { on } },
    )
  ).data

export const adminListPublisherVerifications = async (params: {
  status?: PublisherVerificationStatus
  keyword?: string
  page?: number
  page_size?: number
}): Promise<{ items: PublisherVerification[]; total: number; page: number; page_size: number }> =>
  (await api.get('/information/admin/verifications', { params })).data

export const adminReviewPublisherVerification = async (
  verificationId: number,
  payload: { approved: boolean; reject_reason?: string },
): Promise<PublisherVerification> =>
  (await api.post(`/information/admin/verifications/${verificationId}/review`, payload)).data

export const adminGetPublisherVerificationEvidence = async (
  verificationId: number,
): Promise<PublisherVerificationEvidence> =>
  (await api.get(`/information/admin/verifications/${verificationId}`)).data
