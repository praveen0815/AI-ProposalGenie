import { apiClient } from "./api";
import type { ProposalDetail } from "../types/proposal";
import type {
  ApprovalEvent,
  CostSheet,
  DraftSectionInput,
  RegenerateResult,
  VersionComparison,
  VersionDetail,
  VersionSummary,
} from "../types/workspace";

export async function saveDraft(
  proposalId: string,
  payload: { title: string; expected_revision: number; sections: DraftSectionInput[] },
): Promise<ProposalDetail> {
  const response = await apiClient.put<ProposalDetail>(`/api/v1/proposals/${proposalId}/draft`, payload);
  return response.data;
}

export async function regenerateSection(
  proposalId: string,
  sectionId: string,
  confirmOverwrite: boolean,
): Promise<RegenerateResult> {
  const response = await apiClient.post<RegenerateResult>(
    `/api/v1/proposals/${proposalId}/sections/${sectionId}/regenerate`,
    { confirm_overwrite: confirmOverwrite },
    { timeout: 120000 },
  );
  return response.data;
}

export async function listVersions(proposalId: string): Promise<VersionSummary[]> {
  const response = await apiClient.get<VersionSummary[]>(`/api/v1/proposals/${proposalId}/versions`);
  return response.data;
}

export async function createVersion(proposalId: string, changeDescription: string): Promise<VersionDetail> {
  const response = await apiClient.post<VersionDetail>(`/api/v1/proposals/${proposalId}/versions`, {
    change_description: changeDescription,
  });
  return response.data;
}

export async function compareVersions(proposalId: string, leftId: string, rightId: string): Promise<VersionComparison> {
  const response = await apiClient.get<VersionComparison>(`/api/v1/proposals/${proposalId}/versions/compare`, {
    params: { left_id: leftId, right_id: rightId },
  });
  return response.data;
}

export async function restoreVersion(proposalId: string, versionId: string): Promise<ProposalDetail> {
  const response = await apiClient.post<ProposalDetail>(`/api/v1/proposals/${proposalId}/versions/${versionId}/restore`);
  return response.data;
}

export async function getCosts(proposalId: string): Promise<CostSheet> {
  const response = await apiClient.get<CostSheet>(`/api/v1/proposals/${proposalId}/costs`);
  return response.data;
}

export async function saveCosts(
  proposalId: string,
  payload: { currency: string; lines: Array<Record<string, string>> },
): Promise<CostSheet> {
  const response = await apiClient.put<CostSheet>(`/api/v1/proposals/${proposalId}/costs`, payload);
  return response.data;
}

export async function suggestCosts(proposalId: string, currency: string): Promise<CostSheet> {
  const response = await apiClient.post<CostSheet>(`/api/v1/proposals/${proposalId}/costs/suggest`, null, {
    params: { currency },
    timeout: 120000,
  });
  return response.data;
}

export async function confirmCost(proposalId: string, itemId: string): Promise<CostSheet> {
  const response = await apiClient.post<CostSheet>(`/api/v1/proposals/${proposalId}/costs/items/${itemId}/confirm`);
  return response.data;
}

export async function listApprovals(proposalId: string): Promise<ApprovalEvent[]> {
  const response = await apiClient.get<ApprovalEvent[]>(`/api/v1/proposals/${proposalId}/approval`);
  return response.data;
}

export async function applyApproval(proposalId: string, action: string, comment?: string): Promise<ProposalDetail> {
  const response = await apiClient.post<ProposalDetail>(`/api/v1/proposals/${proposalId}/approval`, {
    action,
    comment: comment || null,
  });
  return response.data;
}
