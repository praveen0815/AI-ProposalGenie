export type MembershipRole = "OWNER" | "ADMIN" | "MEMBER";

export interface Company {
  id: string;
  name: string;
  industry: string | null;
  website: string | null;
  description: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  region: string | null;
  postal_code: string | null;
  country: string | null;
  services: string[];
  expertise: string[];
  brand_tagline: string | null;
  brand_voice: string | null;
  brand_primary_color: string | null;
  role: MembershipRole;
}

export interface CompanyInput {
  name: string;
  industry?: string | null;
  website?: string | null;
  description?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  address_line1?: string | null;
  address_line2?: string | null;
  city?: string | null;
  region?: string | null;
  postal_code?: string | null;
  country?: string | null;
  services?: string[];
  expertise?: string[];
  brand_tagline?: string | null;
  brand_voice?: string | null;
  brand_primary_color?: string | null;
}

export interface Member {
  user_id: string;
  email: string;
  full_name: string;
  role: MembershipRole;
  created_at: string;
}
