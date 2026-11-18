export type AgentNodeState = "pending" | "running" | "completed" | "failed";
export type AgentWorkflowStatus = "NOT_STARTED" | "RUNNING" | "COMPLETED" | "FAILED";

export interface AgentNodeStatus {
  key: string;
  label: string;
  status: AgentNodeState;
}

export interface AgentSource {
  kind: string;
  label: string;
  document_id: string;
  url: string;
}

export interface AgentReview {
  approved?: boolean;
  contradictions?: string[];
  unsupported_claims?: string[];
  unmet_requirements?: string[];
  corrections?: string[];
}

export interface AgentStatus {
  proposal_id: string;
  run_id: string | null;
  status: AgentWorkflowStatus;
  current_node: string | null;
  iteration: number;
  max_iterations: number;
  nodes: AgentNodeStatus[];
  review: AgentReview;
  sources: AgentSource[];
  external_research_status: string | null;
  review_limit_reached: boolean;
  error: string | null;
}

export interface AgentEvent {
  id: string;
  run_id: string;
  node: string;
  phase: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}
