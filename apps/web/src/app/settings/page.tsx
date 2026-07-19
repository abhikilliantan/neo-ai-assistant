import { SettingsView } from "@/features/settings/components/settings-view";

export default function SettingsPage() {
  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Settings</h1>
      <SettingsView />
    </section>
  );
}
