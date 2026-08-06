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
import { SampleTag } from "@/features/redesign/components";
import { round } from "@/features/redesign/components/format";
import { REGIONS } from "./data";

const ICON: Record<string, LucideIcon> = {
  Kenya: MapPin,
  UAE: Briefcase,
  Remote: Users,
  India: Code2,
  Rwanda: FolderKanban,
  Global: Globe,
};

/** Enterprise Overview: a glowing world globe with region nodes overlaid.
 *  Pass `imageSrc` to swap the CSS placeholder for a real globe render. */
export function EnterpriseOverview({ imageSrc }: { imageSrc?: string }) {
  return (
    <div className="glow-card p-5">
      <div className="mb-4 flex items-center gap-2">
        <span className="h-5 w-1 rounded-full bg-rd-grad" aria-hidden />
        <h2 className="text-sm font-semibold uppercase tracking-wide text-rd-heading">
          Enterprise Overview
        </h2>
        <SampleTag />
      </div>

      {/* Globe centered, region nodes in a readable grid below. (The mockup
          flanks the globe, but the flank columns are too narrow for the region
          names at laptop width — the grid keeps every node legible.) */}
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

function Sphere({ imageSrc }: { imageSrc?: string }) {
  return (
    <div className="relative mx-auto flex aspect-square w-full max-w-[240px] items-center justify-center">
      <div
        className="absolute inset-4 rounded-full opacity-60 blur-2xl"
        style={{
          background: "radial-gradient(circle at 50% 40%, hsl(var(--rd-cyan)), transparent 70%)",
        }}
        aria-hidden
      />
      {imageSrc ? (
        // asset hook: real globe render drops in here
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageSrc}
          alt="Enterprise globe"
          className="relative z-10 h-full w-full rounded-full object-contain"
        />
      ) : (
        <div
          className="relative z-10 aspect-square w-[78%] overflow-hidden rounded-full border border-rd-cyan/40"
          style={{
            background:
              "radial-gradient(circle at 42% 32%, rgba(56,189,248,.45), rgba(11,17,32,.95) 72%)",
          }}
          aria-hidden
        >
          {/* meridians / latitudes */}
          <span className="absolute inset-0 rounded-[50%] border border-rd-cyan/20" />
          <span className="absolute inset-x-[30%] inset-y-0 rounded-[50%] border border-rd-cyan/20" />
          <span className="absolute inset-x-[10%] inset-y-0 rounded-[50%] border border-rd-cyan/15" />
          <span className="absolute inset-x-0 inset-y-[30%] rounded-[50%] border border-rd-cyan/20" />
          <span className="absolute inset-x-0 inset-y-[10%] rounded-[50%] border border-rd-cyan/15" />
        </div>
      )}
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
