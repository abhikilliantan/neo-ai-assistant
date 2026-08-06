import { cn } from "@/lib/cn";

const GRADIENTS = [
  "from-rd-cyan to-rd-violet",
  "from-rd-violet to-rd-rose",
  "from-rd-green to-rd-cyan",
  "from-rd-amber to-rd-rose",
  "from-rd-cyan to-rd-green",
];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** Overlapping avatar circles (initials on a gradient) + an optional "+N". */
export function AvatarStack({
  names,
  extra,
  size = 24,
  className,
}: {
  names: string[];
  extra?: number;
  size?: number;
  className?: string;
}) {
  return (
    <div className={cn("flex items-center", className)}>
      <div className="flex -space-x-2">
        {names.map((n, i) => (
          <span
            key={`${n}-${i}`}
            title={n}
            className={cn(
              "flex items-center justify-center rounded-full bg-gradient-to-br font-semibold text-white ring-2 ring-rd-card",
              GRADIENTS[i % GRADIENTS.length],
            )}
            style={{ width: size, height: size, fontSize: size * 0.38 }}
          >
            {initials(n)}
          </span>
        ))}
      </div>
      {extra != null && extra > 0 && (
        <span className="ml-1.5 text-xs font-medium text-rd-muted">+{extra}</span>
      )}
    </div>
  );
}
