"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, subscribeRunEvents } from "@/lib/api";
import type { PipelineReport } from "@/lib/api-types";
import { RunReport } from "@/components/run-report";
import { Card } from "@/components/ui/card";

const STEPS = [
  "planner",
  "research",
  "critic",
  "writer",
  "prepare_citations",
  "validator",
  "controller",
];

export default function RunDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [status, setStatus] = useState("pending");
  const [report, setReport] = useState<PipelineReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    const unsub = subscribeRunEvents(
      id,
      (ev) => {
        if (ev.status === "completed" && STEPS.includes(ev.step)) {
          setCompletedSteps((prev) => [...prev, ev.step]);
        }
      },
      async (finalStatus) => {
        setStatus(finalStatus);
        try {
          const data = await api.getRun(id);
          if (!cancelled) {
            setReport(data.report || null);
            setError(data.error_message || null);
          }
        } catch {
          /* ignore */
        }
      },
    );

    api.getRun(id).then((data) => {
      if (cancelled) return;
      setStatus(data.status);
      if (data.report) setReport(data.report);
      if (data.error_message) setError(data.error_message);
      if (data.status === "completed" || data.status === "failed") {
        unsub();
      }
    });

    return () => {
      cancelled = true;
      unsub();
    };
  }, [id]);

  if (status === "pending" || status === "running") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Analysis in progress…</h1>
        <Card>
          <div className="flex flex-wrap gap-2">
            {STEPS.map((s) => (
              <span
                key={s}
                className={`rounded px-2 py-1 text-xs ${
                  completedSteps.includes(s)
                    ? "bg-verified text-foreground"
                    : "bg-surface text-foreground/50"
                }`}
              >
                {s}
              </span>
            ))}
          </div>
          <p className="mt-4 text-sm text-foreground/60">
            Keep this page open; results will appear when the run completes.
          </p>
        </Card>
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold text-primary">Analysis failed</h1>
        <Card className="bg-not-found/40 text-sm">
          {error || "Research stopped: arXiv and Semantic Scholar both failed."}
        </Card>
      </div>
    );
  }

  if (!report) return <p className="text-sm">Loading…</p>;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">{report.topic}</h1>
      <RunReport report={report} />
    </div>
  );
}
