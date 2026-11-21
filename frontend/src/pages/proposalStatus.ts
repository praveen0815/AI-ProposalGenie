import type { ProposalStatus } from "../types/proposal";

const labels: Record<ProposalStatus, string> = {
  DRAFT: "Draft",
  GENERATING: "Generating",
  REVIEW: "In review",
  APPROVED: "Approved",
  SENT: "Sent",
  REJECTED: "Rejected",
  ARCHIVED: "Archived",
};

export function statusLabel(status: ProposalStatus): string {
  return labels[status];
}
