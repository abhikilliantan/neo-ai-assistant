"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import type { Memory } from "@neo/shared-types";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/relative-time";
import { GlowCard, SectionHeader } from "@/features/redesign/components";
import { createMemory, deleteMemory, listMemories } from "@/services/memories";

// Kinds the backend CHECK allows. "all" is the filter default.
const KINDS = ["fact", "preference", "instruction", "summary", "other"] as const;
type Kind = (typeof KINDS)[number];

const KIND_PILL: Record<string, string> = {
  fact: "border-rd-cyan/40 bg-rd-cyan/10 text-rd-cyan",
  preference: "border-rd-violet/40 bg-rd-violet/10 text-rd-violet",
  instruction: "border-rd-amber/40 bg-rd-amber/10 text-rd-amber",
  summary: "border-rd-green/40 bg-rd-green/10 text-rd-green",
  other: "border-rd-border bg-rd-panel text-rd-muted",
};

export function MemoriesView() {
  const qc = useQueryClient();
  const { data, isLoading, isError } = useQuery({ queryKey: ["memories"], queryFn: listMemories });

  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<"all" | Kind>("all");
  const [draft, setDraft] = useState("");
  const [draftKind, setDraftKind] = useState<Kind>("fact");

  const create = useMutation({
    mutationFn: () => createMemory({ content: draft.trim(), kind: draftKind }),
    onSuccess: () => {
      setDraft("");
      void qc.invalidateQueries({ queryKey: ["memories"] });
    },
  });
  const del = useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["memories"] }),
  });

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (data ?? []).filter(
      (m) => (kind === "all" || m.kind === kind) && (!q || m.content.toLowerCase().includes(q)),
    );
  }, [data, query, kind]);

  return (
    <div className="mx-auto max-w-[1000px] space-y-6">
      <SectionHeader
        title="Memories"
        subtitle="What NEO remembers about you — saved from chat or added here. Search, review, or delete any."
      />

      {/* Add a memory */}
      <GlowCard className="p-4">
        <form
          className="flex flex-wrap items-center gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim()) create.mutate();
          }}
        >
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Add a memory NEO should keep (e.g. “Call me Boss”)…"
            aria-label="New memory content"
            className="h-10 min-w-0 flex-1 rounded-control border border-rd-border bg-rd-panel/60 px-3 text-sm text-rd-heading placeholder:text-rd-muted focus:border-rd-border-hover focus:outline-none focus:ring-2 focus:ring-rd-cyan/30"
          />
          <select
            value={draftKind}
            onChange={(e) => setDraftKind(e.target.value as Kind)}
            aria-label="New memory kind"
            className="h-10 rounded-control border border-rd-border bg-rd-panel/60 px-2.5 text-sm text-rd-body focus:outline-none"
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={draft.trim() === "" || create.isPending}
            className="flex h-10 shrink-0 items-center gap-1.5 rounded-control bg-rd-grad px-3.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Plus className="h-4 w-4" aria-hidden />
            {create.isPending ? "Saving…" : "Add"}
          </button>
        </form>
        {create.isError && (
          <p className="mt-2 text-xs text-rd-rose">Couldn’t save that memory. Try again.</p>
        )}
      </GlowCard>

      {/* Search + kind filter */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1 sm:max-w-sm">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-rd-muted"
            aria-hidden
          />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search memories…"
            aria-label="Search memories"
            className="h-10 w-full rounded-control border border-rd-border bg-rd-panel/60 pl-9 pr-3 text-sm text-rd-heading placeholder:text-rd-muted focus:border-rd-border-hover focus:outline-none focus:ring-2 focus:ring-rd-cyan/30"
          />
        </div>
        <div className="flex flex-wrap items-center gap-1 rounded-control border border-rd-border bg-rd-panel/50 p-1">
          <FilterChip label="All" active={kind === "all"} onClick={() => setKind("all")} />
          {KINDS.map((k) => (
            <FilterChip key={k} label={k} active={kind === k} onClick={() => setKind(k)} />
          ))}
        </div>
      </div>

      {/* List */}
      <div className="space-y-2">
        {isLoading && <p className="text-sm text-rd-muted">Loading…</p>}
        {isError && <p className="text-sm text-rd-rose">Failed to load memories.</p>}
        {data && rows.length === 0 && (
          <GlowCard className="flex flex-col items-center gap-1 py-10 text-center">
            <Brain className="h-7 w-7 text-rd-muted" aria-hidden />
            <p className="text-sm font-medium text-rd-heading">
              {data.length === 0 ? "No memories yet" : "No memories match your filters"}
            </p>
            <p className="text-sm text-rd-muted">
              {data.length === 0
                ? "Tell NEO “remember …” in AI Chat, or add one above."
                : "Try a different search or kind."}
            </p>
          </GlowCard>
        )}
        {rows.map((m) => (
          <MemoryRow
            key={m.id}
            memory={m}
            onDelete={() => del.mutate(m.id)}
            deleting={del.isPending && del.variables === m.id}
          />
        ))}
      </div>
    </div>
  );
}

function MemoryRow({
  memory,
  onDelete,
  deleting,
}: {
  memory: Memory;
  onDelete: () => void;
  deleting: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  return (
    <GlowCard className="flex items-start justify-between gap-4 p-4">
      <div className="min-w-0 flex-1">
        <p className="text-sm text-rd-heading">{memory.content}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-rd-muted">
          <span
            className={cn(
              "rounded-full border px-2 py-0.5 text-[11px] font-medium capitalize",
              KIND_PILL[memory.kind] ?? KIND_PILL.other,
            )}
          >
            {memory.kind}
          </span>
          {memory.source && <span>via {memory.source}</span>}
          <span aria-hidden>·</span>
          <span>{formatRelative(memory.created_at)}</span>
        </div>
      </div>
      {confirming ? (
        <div className="flex shrink-0 items-center gap-2">
          <button
            type="button"
            onClick={onDelete}
            disabled={deleting}
            className="rounded-control border border-rd-rose/40 bg-rd-rose/10 px-2.5 py-1 text-xs font-medium text-rd-rose disabled:opacity-50"
          >
            {deleting ? "Deleting…" : "Confirm"}
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            disabled={deleting}
            className="rounded-control px-2 py-1 text-xs text-rd-muted hover:text-rd-heading disabled:opacity-50"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          aria-label="Delete memory"
          className="shrink-0 rounded-control border border-rd-border p-1.5 text-rd-muted transition-colors hover:border-rd-rose/40 hover:text-rd-rose"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
        </button>
      )}
    </GlowCard>
  );
}

function FilterChip({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md px-2.5 py-1 text-xs font-medium capitalize transition-colors",
        active ? "bg-rd-grad text-white" : "text-rd-muted hover:text-rd-heading",
      )}
    >
      {label}
    </button>
  );
}
