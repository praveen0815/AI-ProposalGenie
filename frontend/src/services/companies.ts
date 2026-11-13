import type { Company, CompanyInput, Member, MembershipRole } from "../types/company";
import { apiClient } from "./api";

export async function listCompanies(): Promise<Company[]> {
  const response = await apiClient.get<Company[]>("/api/v1/companies");
  return response.data;
}

export async function createCompany(input: CompanyInput): Promise<Company> {
  const response = await apiClient.post<Company>("/api/v1/companies", input);
  return response.data;
}

export async function updateCompany(companyId: string, input: CompanyInput): Promise<Company> {
  const response = await apiClient.patch<Company>(`/api/v1/companies/${companyId}`, input);
  return response.data;
}

export async function listMembers(companyId: string): Promise<Member[]> {
  const response = await apiClient.get<Member[]>(`/api/v1/companies/${companyId}/members`);
  return response.data;
}

export async function addMember(companyId: string, email: string, role: MembershipRole): Promise<Member> {
  const response = await apiClient.post<Member>(`/api/v1/companies/${companyId}/members`, { email, role });
  return response.data;
}

export async function updateMemberRole(
  companyId: string,
  userId: string,
  role: MembershipRole,
): Promise<Member> {
  const response = await apiClient.patch<Member>(`/api/v1/companies/${companyId}/members/${userId}`, { role });
  return response.data;
}
