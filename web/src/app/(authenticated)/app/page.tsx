"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";
import type { PipelineReport } from "@/lib/api-types";
import { RunReport } from "@/components/run-report";

export default function WorkspacePage() {
  const router = useRouter();
  const [topic, setTopic] = useState("");
  const [yearMin, setYearMin] = useState(2018);
  const [yearMax, setYearMax] = useState(2026);
  const [domain, setDomain] = useState("");
  const [minCards, setMinCards] = useState(10);
  const [perSource, setPerSource] = useState(15);
  const [loading, setLoading] = useState(false);
  const [steps, setSteps] = useState<string[]>([]);
  const [demo, setDemo] = useState<PipelineReport | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setSteps([]);
    setDemo(null);
    try {
      const constraints: Record<string, unknown> = {
        min_cards: minCards,
        per_source_limit: perSource,
        year_min: yearMin,
        year_max: yearMax,
      };
      if (domain.trim()) constraints.domain = domain.trim();
      const { id } = await api.createRun(topic.trim(), constraints);
      router.push(`/app/runs/${id}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start run");
      setLoading(false);
    }
  }

  async function loadDemo() {
    try {
      const res = await fetch("/api/demo-report");
      if (!res.ok) throw new Error("not found");
      setDemo((await res.json()) as PipelineReport);
      toast.success("Demo report loaded");
    } catch {
      toast.error("Demo report unavailable");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">Workspace</h1>
      <Card>
        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="text-xs font-medium">Research topic</label>
            <input
              className="mt-1 w-full rounded border border-surface px-3 py-2 text-sm"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. retrieval augmented generation"
              required
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs font-medium">Year from</label>
              <input
                type="number"
                className="mt-1 w-full rounded border border-surface px-3 py-2 text-sm"
                value={yearMin}
                onChange={(e) => setYearMin(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Year to</label>
              <input
                type="number"
                className="mt-1 w-full rounded border border-surface px-3 py-2 text-sm"
                value={yearMax}
                onChange={(e) => setYearMax(Number(e.target.value))}
              />
            </div>
          </div>
          <div>
            <label className="text-xs font-medium">Domain (optional)</label>
            <input
              className="mt-1 w-full rounded border border-surface px-3 py-2 text-sm"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="NLP, systems..."
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="text-xs font-medium">Minimum papers</label>
              <input
                type="number"
                className="mt-1 w-full rounded border border-surface px-3 py-2 text-sm"
                value={minCards}
                onChange={(e) => setMinCards(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="text-xs font-medium">Max per source</label>
              <input
                type="number"
                className="mt-1 w-full rounded border border-surface px-3 py-2 text-sm"
                value={perSource}
                onChange={(e) => setPerSource(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button type="submit" disabled={loading}>
              {loading ? "Starting…" : "Start analysis"}
            </Button>
            <Button type="button" variant="outline" onClick={loadDemo}>
              Load demo report
            </Button>
          </div>
        </form>
      </Card>
      {loading && steps.length > 0 && (
        <Card>
          <p className="text-sm font-medium">Progress</p>
          <ul className="mt-2 text-sm">
            {steps.map((s) => (
              <li key={s}>✓ {s}</li>
            ))}
          </ul>
        </Card>
      )}
      {demo && <RunReport report={demo} />}
    </div>
  );
}
