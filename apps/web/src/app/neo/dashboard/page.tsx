import { DashboardView } from "@/features/redesign/dashboard/DashboardView";

// Static /neo/dashboard wins over the dynamic [section] placeholder.
export const metadata = { title: "Dashboard — NEO" };

export default function DashboardPage() {
  return <DashboardView />;
}
