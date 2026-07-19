"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { Memory, Preference } from "@neo/shared-types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { formatRelative } from "@/lib/relative-time";
import { deleteMemory, listMemories, listPreferences, upsertPreference } from "@/services/memories";

export function SettingsView() {
  return (
    <div className="space-y-6">
      <MemoriesCard />
      <PreferencesCard />
    </div>
  );
}

// --- memories --------------------------------------------------------------

function MemoriesCard() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["memories"],
    queryFn: listMemories,
  });

  const del = useMutation({
    mutationFn: (id: string) => deleteMemory(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["memories"] }),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>What Neo remembers</CardTitle>
      </CardHeader>
      <CardContent>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="text-sm text-red-500">Failed to load memories.</p>}
        {data && data.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Neo hasn&apos;t remembered anything about you yet.
          </p>
        )}
        {data && data.length > 0 && (
          <ul className="space-y-2">
            {data.map((m) => (
              <MemoryRow
                key={m.id}
                memory={m}
                onDelete={() => del.mutate(m.id)}
                deleting={del.isPending && del.variables === m.id}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
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
  return (
    <li className="flex items-start justify-between gap-3 rounded-md border px-3 py-2">
      <div className="min-w-0 flex-1 space-y-1">
        <p className="break-words text-sm">{memory.content}</p>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <Badge>{memory.kind}</Badge>
          {memory.source && <Badge>{memory.source}</Badge>}
          <span>{formatRelative(memory.created_at)}</span>
        </div>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onDelete}
        disabled={deleting}
        aria-label={`Delete memory: ${memory.content}`}
      >
        {deleting ? "Deleting…" : "Delete"}
      </Button>
    </li>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wide">
      {children}
    </span>
  );
}

// --- preferences -----------------------------------------------------------

function PreferencesCard() {
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useQuery({
    queryKey: ["preferences"],
    queryFn: listPreferences,
  });

  const [key, setKey] = useState("");
  const [value, setValue] = useState("");

  const upsert = useMutation({
    mutationFn: (input: { key: string; value: string }) => upsertPreference(input.key, input.value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["preferences"] });
      setKey("");
      setValue("");
    },
  });

  function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmedKey = key.trim();
    if (!trimmedKey) return;
    upsert.mutate({ key: trimmedKey, value });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Preferences</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {isError && <p className="text-sm text-red-500">Failed to load preferences.</p>}
        {data && data.length === 0 && (
          <p className="text-sm text-muted-foreground">No preferences saved yet.</p>
        )}
        {data && data.length > 0 && (
          <ul className="space-y-2">
            {data.map((p) => (
              <PreferenceRow key={p.key} preference={p} />
            ))}
          </ul>
        )}

        <form className="space-y-2 pt-2" onSubmit={onSubmit} noValidate>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <div className="space-y-1">
              <label className="text-xs font-medium" htmlFor="pref-key">
                Key
              </label>
              <Input
                id="pref-key"
                value={key}
                onChange={(e) => setKey(e.target.value)}
                placeholder="tone"
                disabled={upsert.isPending}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium" htmlFor="pref-value">
                Value
              </label>
              <Input
                id="pref-value"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="concise"
                disabled={upsert.isPending}
              />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button type="submit" size="sm" disabled={upsert.isPending || key.trim() === ""}>
              {upsert.isPending ? "Saving…" : "Save"}
            </Button>
            {upsert.isError && <p className="text-xs text-red-500">Could not save preference.</p>}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function PreferenceRow({ preference }: { preference: Preference }) {
  const display =
    typeof preference.value === "string" ? preference.value : JSON.stringify(preference.value);
  return (
    <li className="flex items-start justify-between gap-3 rounded-md border px-3 py-2 text-sm">
      <span className="font-mono text-xs text-muted-foreground">{preference.key}</span>
      <span className="min-w-0 flex-1 break-words text-right">{display}</span>
    </li>
  );
}
