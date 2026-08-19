import api from './api'
import type {
  InfoCategory,
  InfoStatus,
  InformationAdminPost,
  InformationMinePost,
  InformationPage,
  InformationPostDetail,
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
  contact_phone?: string
  content: string
  attributes?: Record<string, string>
}

export const createInformation = async (payload: InformationCreatePayload): Promise<InformationMinePost> =>
  (await api.post<InformationMinePost>('/information', payload)).data

export const listMyInformation = async (): Promise<InformationMinePost[]> =>
  (await api.get<InformationMinePost[]>('/information/mine')).data

export const deleteInformation = async (postId: number): Promise<{ deleted: boolean }> =>
  (await api.delete<{ deleted: boolean }>(`/information/${postId}`)).data

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
