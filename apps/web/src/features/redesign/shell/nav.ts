import type { Route } from "next";
import type { LucideIcon } from "lucide-react";
import {
  BarChart3,
  Bot,
  Building2,
  ClipboardList,
  Code2,
  DollarSign,
  FileText,
  FolderKanban,
  LayoutDashboard,
  MessageSquare,
  Megaphone,
  Network,
  Presentation,
  Rocket,
  Settings,
  TrendingUp,
  UserCog,
  Users,
  Video,
  Workflow,
  BookOpen,
} from "lucide-react";

export interface NavItem {
  slug: string;
  label: string;
  icon: LucideIcon;
  /** Decorative chevron (marks a section that will gain a submenu later). */
  chevron?: boolean;
}

export interface NavGroup {
  label?: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Main",
    items: [
      { slug: "dashboard", label: "Dashboard", icon: LayoutDashboard },
      { slug: "executive-briefing", label: "Executive Briefing", icon: Presentation },
      { slug: "ai-chat", label: "AI Chat", icon: MessageSquare },
    ],
  },
  {
    label: "Organization",
    items: [
      { slug: "companies", label: "Companies", icon: Building2, chevron: true },
      { slug: "projects", label: "Projects", icon: FolderKanban, chevron: true },
      { slug: "departments", label: "Departments", icon: Network, chevron: true },
      { slug: "people", label: "People", icon: Users },
      { slug: "meetings", label: "Meetings", icon: Video },
    ],
  },
  {
    label: "Business",
    items: [
      { slug: "sales", label: "Sales", icon: TrendingUp, chevron: true },
      { slug: "marketing", label: "Marketing", icon: Megaphone, chevron: true },
      { slug: "finance", label: "Finance", icon: DollarSign },
      { slug: "hr", label: "HR", icon: UserCog },
    ],
  },
  {
    label: "Delivery",
    items: [
      { slug: "development", label: "Development", icon: Code2 },
      { slug: "implementation", label: "Implementation", icon: Rocket },
      { slug: "documents", label: "Documents", icon: FileText },
      { slug: "knowledge-base", label: "Knowledge Base", icon: BookOpen },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { slug: "ai-agents", label: "AI Agents", icon: Bot },
      { slug: "automation", label: "Automation", icon: Workflow },
      { slug: "analytics", label: "Analytics", icon: BarChart3 },
      { slug: "reports", label: "Reports", icon: ClipboardList },
    ],
  },
  {
    items: [{ slug: "settings", label: "Settings", icon: Settings }],
  },
];

export const NAV_ITEMS: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

export function navHref(slug: string): Route {
  return `/neo/${slug}` as Route;
}

export function findNavItem(slug: string): NavItem | undefined {
  return NAV_ITEMS.find((i) => i.slug === slug);
}
