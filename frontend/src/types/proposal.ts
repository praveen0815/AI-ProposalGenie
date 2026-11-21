export type ProposalStatus = "DRAFT" | "GENERATING" | "REVIEW" | "APPROVED" | "SENT" | "REJECTED" | "ARCHIVED";

export interface ProposalInput {
  company_id: string;
  client_name: string;
  client_industry?: string;
  client_requirements: string;
  project_title: string;
  project_description?: string;
  business_objectives?: string;
  scope_of_work?: string;
  deliverables?: string;
  timeline?: string;
  budget_range?: string;
  currency?: string;
  payment_terms?: string;
  additional_instructions?: string;
}

export interface SourceReference {
  document_id: string;
  filename: string;
  chunk_index: number | null;
}

export interface TokenUsage {
  prompt_tokens: number | null;
  completion_tokens: number | null;
  total_tokens: number | null;
}

export interface ProposalSection {
  id: string;
  title: string;
  body: string;
  position: number;
  needs_review: boolean;
  review_notes: string | null;
  ai_body: string | null;
  origin: string;
  source_references: SourceReference[];
}

export interface ProposalSummary {
  id: string;
  company_id: string;
  title: string;
  summary: string | null;
  status: ProposalStatus;
  client_name: string | null;
  generation_error: string | null;
  generated_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProposalDetail extends ProposalSummary {
  client_id: string | null;
  content_revision: number;
  model_name: string | null;
  prompt_version: string | null;
  retrieval_status: string | null;
  token_usage: TokenUsage | null;
  generation_input: ProposalInput | null;
  source_references: SourceReference[];
  sections: ProposalSection[];
}
