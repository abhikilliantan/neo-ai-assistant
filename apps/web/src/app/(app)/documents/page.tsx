import { DocumentsView } from "@/features/documents/components/documents-view";

export default function DocumentsPage() {
  return (
    <section className="space-y-6">
      <h1 className="text-2xl font-semibold">Documents</h1>
      <DocumentsView />
    </section>
  );
}
