import { DashboardView } from "@/features/dashboard/components/dashboard-view";

export default function DashboardPage() {
  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <DashboardView />
    </section>
  );
}
