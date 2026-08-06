import Link from "next/link";
import type { Route } from "next";
import {
  BookOpen,
  Building2,
  CalendarClock,
  Code2,
  DollarSign,
  FileText,
  FolderKanban,
  Megaphone,
  TrendingUp,
  UserCog,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { navHref } from "@/features/redesign/shell";

interface Node {
  label: string;
  icon: LucideIcon;
  href: Route;
}

const LEFT: Node[] = [
  { label: "Sales", icon: TrendingUp, href: navHref("sales") },
  { label: "Finance", icon: DollarSign, href: navHref("finance") },
  { label: "Marketing", icon: Megaphone, href: navHref("marketing") },
  { label: "HR", icon: UserCog, href: navHref("hr") },
  { label: "Development", icon: Code2, href: navHref("development") },
];

const RIGHT: Node[] = [
  { label: "Projects", icon: FolderKanban, href: navHref("projects") },
  { label: "Customers", icon: Building2, href: navHref("companies") },
  { label: "Knowledge", icon: BookOpen, href: navHref("knowledge-base") },
  { label: "Documents", icon: FileText, href: navHref("documents") },
  { label: "Calendar", icon: CalendarClock, href: navHref("meetings") },
];

/** The glowing NEO "brain" hero. CSS/SVG core by default; pass `imageSrc` to
 *  drop in a real brain asset later (rendered over the core, rings kept as a
 *  glowing frame). Module nodes are REAL navigation links. */
export function NeoBrain({ imageSrc }: { imageSrc?: string }) {
  return (
    <div className="grid grid-cols-[auto_1fr_auto] items-center gap-3 sm:gap-5">
      <div className="flex flex-col gap-2">
        {LEFT.map((n) => (
          <NodeLink key={n.label} node={n} side="left" />
        ))}
      </div>

      <Core imageSrc={imageSrc} />

      <div className="flex flex-col gap-2">
        {RIGHT.map((n) => (
          <NodeLink key={n.label} node={n} side="right" />
        ))}
      </div>
    </div>
  );
}

function Core({ imageSrc }: { imageSrc?: string }) {
  return (
    <div className="relative mx-auto flex aspect-square w-full max-w-[220px] items-center justify-center">
      {/* radial glow */}
      <div
        className="absolute inset-0 rounded-full opacity-70 blur-2xl"
        style={{ background: "var(--rd-grad)" }}
        aria-hidden
      />
      {/* concentric rings */}
      <div className="absolute inset-2 rounded-full border border-rd-border-hover/60" aria-hidden />
      <div className="absolute inset-6 rounded-full border border-rd-border" aria-hidden />
      <div className="gradient-ring absolute inset-10 rounded-full" aria-hidden />

      {/* asset hook: replace this inner disc with a real brain image via imageSrc */}
      {imageSrc ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={imageSrc}
          alt="NEO core"
          className="relative z-10 h-24 w-24 rounded-full object-cover"
        />
      ) : (
        <div className="relative z-10 flex h-24 w-24 items-center justify-center rounded-full border border-rd-border-hover bg-rd-base/70 backdrop-blur-sm">
          <span className="bg-rd-grad bg-clip-text text-lg font-bold tracking-[0.2em] text-transparent">
            NEO
          </span>
        </div>
      )}
    </div>
  );
}

function NodeLink({ node, side }: { node: Node; side: "left" | "right" }) {
  const Icon = node.icon;
  return (
    <Link
      href={node.href}
      className={cn(
        "group flex items-center gap-2 rounded-full border border-rd-border bg-rd-card/70 px-2.5 py-1.5 text-xs text-rd-body transition-colors",
        "hover:border-rd-border-hover hover:text-rd-heading focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rd-cyan/60",
        side === "right" && "flex-row-reverse text-right",
      )}
    >
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-rd-border bg-rd-panel text-rd-cyan">
        <Icon className="h-3.5 w-3.5" aria-hidden />
      </span>
      <span className="truncate">{node.label}</span>
    </Link>
  );
}
