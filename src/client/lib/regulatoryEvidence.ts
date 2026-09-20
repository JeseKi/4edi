import api from './api'
import type {
  RegulatoryEvidence,
  RegulatoryEvidenceLink,
  RegulatoryEvidenceLinkCreated,
  RegulatoryEvidenceType,
} from './types'

export const createRegulatoryEvidenceLink = async (
  evidenceType: RegulatoryEvidenceType,
  resourceId: number,
): Promise<RegulatoryEvidenceLinkCreated> => (
  await api.post<RegulatoryEvidenceLinkCreated>('/regulatory-evidence/admin/links', {
    evidence_type: evidenceType,
    resource_id: resourceId,
  })
).data

export const listRegulatoryEvidenceLinks = async (
  evidenceType: RegulatoryEvidenceType,
  resourceId: number,
): Promise<RegulatoryEvidenceLink[]> => (
  await api.get<RegulatoryEvidenceLink[]>('/regulatory-evidence/admin/links', {
    params: { evidence_type: evidenceType, resource_id: resourceId },
  })
).data

export const revokeRegulatoryEvidenceLink = async (
  linkId: number,
): Promise<RegulatoryEvidenceLink> => (
  await api.post<RegulatoryEvidenceLink>(`/regulatory-evidence/admin/links/${linkId}/revoke`)
).data

export const getRegulatoryEvidence = async (token: string): Promise<RegulatoryEvidence> => (
  await api.get<RegulatoryEvidence>('/regulatory-evidence', {
    headers: { 'X-Regulatory-Evidence-Token': token },
  })
).data
