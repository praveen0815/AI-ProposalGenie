import { apiClient } from "./api";
import type { AgentEvent, AgentStatus } from "../types/agent";

export async function getAgentStatus(proposalId: string): Promise<AgentStatus> {
  const response = await apiClient.get<AgentStatus>(`/api/v1/agents/proposals/${proposalId}/status`);
  return response.data;
}

export async function getAgentHistory(proposalId: string): Promise<AgentEvent[]> {
  const response = await apiClient.get<AgentEvent[]>(`/api/v1/agents/proposals/${proposalId}/history`);
  return response.data;
}

export async function runAgentWorkflow(proposalId: string): Promise<AgentStatus> {
  const response = await apiClient.post<AgentStatus>(`/api/v1/agents/proposals/${proposalId}/run`, null, { timeout: 180000 });
  return response.data;
}

export async function resumeAgentWorkflow(proposalId: string): Promise<AgentStatus> {
  const response = await apiClient.post<AgentStatus>(`/api/v1/agents/proposals/${proposalId}/resume`, null, { timeout: 180000 });
  return response.data;
}
