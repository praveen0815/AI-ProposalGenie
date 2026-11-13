import { BookOpen, Building2, FilePlus2, Files, LayoutDashboard, Settings } from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

export const navItems: NavItem[] = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/proposals", label: "Proposals", icon: Files, end: true },
  { to: "/proposals/new", label: "Create Proposal", icon: FilePlus2, end: true },
  { to: "/knowledge", label: "Company Knowledge", icon: BookOpen, end: true },
  { to: "/company", label: "Company", icon: Building2, end: false },
  { to: "/settings", label: "Settings", icon: Settings, end: true },
];

const pageTitles: { path: string; label: string }[] = [
  { path: "/company/new", label: "Create company" },
  { path: "/company/settings", label: "Company settings" },
  { path: "/company", label: "Company" },
  { path: "/proposals/new", label: "Create Proposal" },
  { path: "/proposals", label: "Proposals" },
  { path: "/knowledge", label: "Company Knowledge" },
  { path: "/settings", label: "Settings" },
  { path: "/", label: "Dashboard" },
];

export function pageTitle(pathname: string): string {
  return pageTitles.find((item) => item.path === pathname)?.label ?? "Not found";
}
