import api from './api'

export interface ComplaintCreatePayload {
  subject: string
  content: string
  contact?: string
}

export interface ComplaintOut {
  id: number
  subject: string
  content: string
  contact: string | null
  status: string
  created_at: string
}

export const createComplaint = async (
  payload: ComplaintCreatePayload,
): Promise<ComplaintOut> =>
  (await api.post<ComplaintOut>('/complaint', payload)).data
