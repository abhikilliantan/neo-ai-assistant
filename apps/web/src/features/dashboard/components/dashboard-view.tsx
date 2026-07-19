"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchHealth } from "@/services/system";

export function DashboardView() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["system", "health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  return (
    <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
      <Card>
        <CardHeader>
          <CardTitle>API status</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && <p className="text-sm text-muted-foreground">Checking…</p>}
          {isError && <p className="text-sm text-red-500">Unreachable</p>}
          {data && (
            <p className="text-sm">
              <span className="font-medium">{data.status}</span>{" "}
              <span className="text-muted-foreground">v{data.version}</span>
            </p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Conversations</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">—</p>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Agents</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-2xl font-semibold">—</p>
        </CardContent>
      </Card>
    </div>
  );
}
