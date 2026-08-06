import {
  Briefcase,
  Code2,
  FolderKanban,
  Globe,
  MapPin,
  Users,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { round } from "@/features/redesign/components/format";
import { REGIONS } from "./data";
import { SectionSampleChip } from "./DemoMode";

const ICON: Record<string, LucideIcon> = {
  Kenya: MapPin,
  UAE: Briefcase,
  Remote: Users,
  India: Code2,
  Rwanda: FolderKanban,
  Global: Globe,
};

/** Enterprise Overview: a glowing world globe with region nodes.
 *  `imageSrc` defaults to the shipped globe render (black bg dropped via
 *  mix-blend screen); pass another path to swap it. */
export function EnterpriseOverview({ imageSrc = "/enterprise-globe.png" }: { imageSrc?: string }) {
  return (
    <div className="glow-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-5 w-1 rounded-full bg-rd-grad" aria-hidden />
        <h2 className="text-sm font-semibold uppercase tracking-wide text-rd-heading">
          Enterprise Overview
        </h2>
        <SectionSampleChip />
      </div>

      {/* Globe centered, region nodes in a readable grid below. */}
      <div className="flex flex-col items-center">
        <Sphere imageSrc={imageSrc} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2.5">
        {REGIONS.map((r) => (
          <RegionNode key={r.name} {...r} />
        ))}
      </div>
    </div>
  );
}

function Sphere({ imageSrc }: { imageSrc: string }) {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[260px]">
      {/* mix-blend screen drops the image's black background so only the glow
          shows over the dark panel — no visible bounding box. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={imageSrc}
        alt="Enterprise operations globe"
        className="h-full w-full object-contain"
        style={{ mixBlendMode: "screen" }}
      />
    </div>
  );
}

function RegionNode({ name, role, percent }: { name: string; role: string; percent: number }) {
  const Icon = ICON[name] ?? Globe;
  return (
    <div className="flex items-center gap-2 rounded-control border border-rd-border bg-rd-card/60 px-2.5 py-1.5">
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-rd-border bg-rd-panel text-rd-cyan">
        <Icon className="h-3.5 w-3.5" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium leading-tight text-rd-heading">{name}</p>
        <p className="truncate text-[10px] leading-tight text-rd-muted">{role}</p>
      </div>
      <span className={cn("shrink-0 text-[13px] font-semibold tabular-nums text-rd-green")}>
        {round(percent)}%
      </span>
    </div>
  );
}
