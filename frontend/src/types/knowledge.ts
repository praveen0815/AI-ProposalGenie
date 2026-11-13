export type DocumentFileType = "PDF" | "DOCX" | "TXT" | "MARKDOWN";

export type DocumentProcessingStatus = "UPLOADED" | "PROCESSING" | "COMPLETED" | "FAILED";

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
  created_at: string;
  updated_at: string;
}
