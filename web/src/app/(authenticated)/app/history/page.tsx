"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { RunSummary } from "@/lib/api-types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);

  function refresh() {
    api.listRuns().then((r) => setRuns(r.runs)).catch(() => toast.error("Failed to load history"));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function remove(id: string) {
    if (!confirm("Delete this run?")) return;
    await api.deleteRun(id);
    refresh();
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-2xl font-bold">History</h1>
      {runs.length === 0 && (
        <p className="text-sm text-foreground/60">
          No runs yet. Go to Workspace to start your first analysis.
        </p>
      )}
      {runs.map((run) => (
        <Card key={run.id} className="flex items-center justify-between gap-4">
          <div>
            <Link href={`/app/runs/${run.id}`} className="font-medium text-primary hover:underline">
              {run.topic}
            </Link>
            <p className="text-xs text-foreground/60">
              {run.status} · {run.paper_count ?? 0} papers · {new Date(run.created_at).toLocaleString()}
            </p>
          </div>
          <Button type="button" variant="ghost" className="text-xs" onClick={() => remove(run.id)}>
            Delete
          </Button>
        </Card>
      ))}
    </div>
  );
}
