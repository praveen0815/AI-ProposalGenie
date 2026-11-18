import { apiClient } from "./api";
import type { ProposalDetail, ProposalInput, ProposalSummary } from "../types/proposal";

export async function listProposals(companyId: string): Promise<ProposalSummary[]> {
  const response = await apiClient.get<ProposalSummary[]>("/api/v1/proposals", { params: { company_id: companyId } });
  return response.data;
}

export async function getProposal(proposalId: string): Promise<ProposalDetail> {
  const response = await apiClient.get<ProposalDetail>(`/api/v1/proposals/${proposalId}`);
  return response.data;
}

export async function createProposal(input: ProposalInput): Promise<ProposalDetail> {
  const response = await apiClient.post<ProposalDetail>("/api/v1/proposals", input);
  return response.data;
}

export async function generateProposal(proposalId: string): Promise<ProposalDetail> {
  const response = await apiClient.post<ProposalDetail>(`/api/v1/proposals/${proposalId}/generate`, null, {
    timeout: 120000,
  });
  return response.data;
}

export async function deleteProposal(proposalId: string): Promise<void> {
  await apiClient.delete(`/api/v1/proposals/${proposalId}`);
}
