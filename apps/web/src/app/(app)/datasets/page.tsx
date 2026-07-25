import { DatasetsView } from "@/features/datasets/components/datasets-view";

export default function DatasetsPage() {
  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Datasets</h1>
      <DatasetsView />
    </section>
  );
}
