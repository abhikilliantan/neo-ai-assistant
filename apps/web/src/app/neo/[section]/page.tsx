import { notFound } from "next/navigation";
import { GlowCard, SampleTag } from "@/features/redesign/components";
import { findNavItem } from "@/features/redesign/shell";

// One placeholder for every nav item (kept as a single dynamic route instead of
// 21 near-identical files). Real content lands per-page in Phase 2+.
export default async function SectionPage({ params }: { params: Promise<{ section: string }> }) {
  const { section } = await params;
  const item = findNavItem(section);
  if (!item) notFound();

  const Icon = item.icon;
  const note =
    item.slug === "dashboard"
      ? "Dashboard — coming in Phase 2."
      : `${item.label} — placeholder page. Content arrives in a later phase.`;

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-center gap-3">
        <span className="gradient-ring relative flex h-11 w-11 items-center justify-center rounded-xl bg-rd-card text-rd-cyan">
          <Icon className="h-5 w-5" aria-hidden />
        </span>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-rd-heading">{item.label}</h1>
            <SampleTag />
          </div>
          <p className="mt-0.5 text-sm text-rd-body">{note}</p>
        </div>
      </div>

      <GlowCard className="flex min-h-[240px] items-center justify-center text-center">
        <div className="max-w-sm">
          <Icon className="mx-auto h-8 w-8 text-rd-muted" aria-hidden />
          <p className="mt-3 text-sm text-rd-body">
            The <span className="text-rd-heading">{item.label}</span> workspace will be built on the
            Phase&nbsp;0 primitive kit. This is the Phase&nbsp;1 shell — navigation works
            end-to-end.
          </p>
        </div>
      </GlowCard>
    </div>
  );
}
