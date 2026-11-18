import { apiClient } from "./api";
import type { IndexResult, KnowledgeDocument, QueryResult, SearchResult } from "../types/knowledge";

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

export async function indexDocument(documentId: string): Promise<IndexResult> {
  const response = await apiClient.post<IndexResult>(`/api/v1/rag/index/document/${documentId}`);
  return response.data;
}

export async function reindexDocument(documentId: string): Promise<IndexResult> {
  const response = await apiClient.post<IndexResult>(`/api/v1/rag/reindex/document/${documentId}`);
  return response.data;
}

export async function searchKnowledge(companyId: string, query: string): Promise<SearchResult> {
  const response = await apiClient.post<SearchResult>("/api/v1/rag/search", {
    company_id: companyId,
    query,
  });
  return response.data;
}

export async function askKnowledge(companyId: string, question: string): Promise<QueryResult> {
  const response = await apiClient.post<QueryResult>("/api/v1/rag/query", {
    company_id: companyId,
    question,
  }, { timeout: 60000 });
  return response.data;
}
