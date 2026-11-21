import type { ProposalDetail, ProposalSection, ProposalStatus } from "./proposal";

export interface VersionSummary {
  id: string;
  proposal_id: string;
  version_number: number;
  change_description: string | null;
  created_by_id: string | null;
  created_at: string;
}

export interface VersionDetail extends VersionSummary {
  snapshot: {
    title?: string;
    sections?: Array<{ title?: string; body?: string }>;
  };
}

export interface VersionChange {
  title: string;
  change: string;
  left: string | null;
  right: string | null;
}

export interface VersionComparison {
  left_version_id: string;
  right_version_id: string;
  title_changed: boolean;
  changes: VersionChange[];
}

export interface RegenerateResult {
  applied: boolean;
  suggested_body: string;
  previous_body: string;
  ai_body: string | null;
  section: ProposalSection | null;
  proposal: ProposalDetail | null;
}

export type CostSource = "ESTIMATED" | "CONFIRMED";

export interface CostLine {
  id: string;
  name: string;
  category: string;
  quantity: string;
  unit: string;
  unit_price: string;
  duration: string;
  tax_percent: string;
  discount_percent: string;
  currency: string;
  source: CostSource;
  base: string;
  discount: string;
  tax: string;
  subtotal: string;
  position: number;
  confirmed_at: string | null;
}

export interface CostSheet {
  currency: string | null;
  lines: CostLine[];
  base: string;
  discount: string;
  tax: string;
  grand_total: string;
  estimated_count: number;
  confirmed_count: number;
}

export interface ApprovalEvent {
  id: string;
  action: string;
  from_status: ProposalStatus;
  to_status: ProposalStatus;
  comment: string | null;
  actor_id: string | null;
  created_at: string;
}

export interface DraftSectionInput {
  id?: string;
  title: string;
  body: string;
}
