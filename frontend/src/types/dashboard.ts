import type { ProposalStatus } from "./proposal";

export interface BudgetSummary {
  currency: string;
  grand_total: string;
  proposal_count: number;
}

export interface RecentProposal {
  id: string;
  title: string;
  status: ProposalStatus;
  client_name: string | null;
  updated_at: string;
}

export interface DashboardSummary {
  company_id: string;
  total: number;
  draft: number;
  awaiting_review: number;
  approved: number;
  sent: number;
  archived: number;
  rejected: number;
  generating: number;
  conversion_rate: string | null;
  budgets: BudgetSummary[];
  recent: RecentProposal[];
}

export interface TrendPoint {
  month: string;
  count: number;
}

export interface StatusCount {
  status: ProposalStatus;
  count: number;
}
