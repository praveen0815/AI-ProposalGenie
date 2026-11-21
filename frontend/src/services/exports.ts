import { apiClient } from "./api";
import type { ProposalExportRecord } from "../types/export";

export async function listExports(proposalId: string): Promise<ProposalExportRecord[]> {
  const response = await apiClient.get<ProposalExportRecord[]>(`/api/v1/proposals/${proposalId}/exports`);
  return response.data;
}

export async function createExport(proposalId: string, format: "pdf" | "docx"): Promise<ProposalExportRecord> {
  const response = await apiClient.post<ProposalExportRecord>(`/api/v1/proposals/${proposalId}/export/${format}`, null, {
    timeout: 60000,
  });
  return response.data;
}

export async function downloadExport(proposalId: string, exportId: string, filename: string): Promise<void> {
  const response = await apiClient.get<Blob>(`/api/v1/proposals/${proposalId}/exports/${exportId}/download`, {
    responseType: "blob",
    timeout: 60000,
  });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
