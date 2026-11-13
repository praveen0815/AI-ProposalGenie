import { apiClient } from "./api";
import type { KnowledgeDocument } from "../types/knowledge";

export async function listDocuments(companyId: string): Promise<KnowledgeDocument[]> {
  const response = await apiClient.get<KnowledgeDocument[]>("/api/v1/knowledge/documents", {
    params: { company_id: companyId },
  });
  return response.data;
}

export async function uploadDocument(
  companyId: string,
  file: File,
  onProgress: (percent: number) => void,
): Promise<KnowledgeDocument> {
  const body = new FormData();
  body.append("file", file);
  const response = await apiClient.post<KnowledgeDocument>("/api/v1/knowledge/documents/upload", body, {
    params: { company_id: companyId },
    timeout: 120000,
    onUploadProgress: (event) => {
      if (!event.total) {
        return;
      }
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    },
  });
  return response.data;
}

export async function deleteDocument(documentId: string): Promise<void> {
  await apiClient.delete(`/api/v1/knowledge/documents/${documentId}`);
}

export async function reprocessDocument(documentId: string): Promise<KnowledgeDocument> {
  const response = await apiClient.post<KnowledgeDocument>(`/api/v1/knowledge/documents/${documentId}/reprocess`);
  return response.data;
}
