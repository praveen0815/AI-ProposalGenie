export interface ProposalExportRecord {
  id: string;
  proposal_id: string;
  format: "PDF" | "DOCX";
  filename: string;
  content_type: string;
  size_bytes: number;
  content_revision: number;
  current_revision: number;
  stale: boolean;
  created_at: string;
}
