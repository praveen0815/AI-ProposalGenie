export type DocumentFileType = "PDF" | "DOCX" | "TXT" | "MARKDOWN";

export type DocumentProcessingStatus = "UPLOADED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type IndexStatus = "NOT_INDEXED" | "INDEXING" | "INDEXED" | "FAILED";

export interface KnowledgeDocument {
  id: string;
  company_id: string;
  uploaded_by_id: string | null;
  original_filename: string;
  file_type: DocumentFileType;
  file_size: number;
  processing_status: DocumentProcessingStatus;
  character_count: number | null;
  page_count: number | null;
  processing_error: string | null;
  index_status: IndexStatus;
  index_error: string | null;
  indexed_at: string | null;
  chunk_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface RetrievedChunk {
  document_id: string;
  filename: string;
  chunk_index: number;
  page_number: number | null;
  source: string;
  text: string;
  score: number;
}

export interface SourceDocument {
  document_id: string;
  filename: string;
  chunk_indexes: number[];
}

export interface SearchResult {
  results: RetrievedChunk[];
}

export interface QueryResult {
  answer: string;
  context: RetrievedChunk[];
  sources: SourceDocument[];
}

export interface IndexResult {
  document_id: string;
  index_status: IndexStatus;
  chunk_count: number | null;
  index_error: string | null;
  indexed_at: string | null;
  already_indexed: boolean;
}
