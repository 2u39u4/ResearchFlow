"use client";

import { useState } from "react";
import type { PipelineReport } from "@/lib/api-types";
import { t, type Locale } from "@/lib/i18n";
import { CitationBadge } from "./citation-badge";
import { PaperCard } from "./paper-card";
import { Card } from "./ui/card";
import { Button } from "./ui/button";

const CRITIQUE_LABELS: Record<string, string> = {
  gap: "Research gap",
  weakness: "Weakness",
  novelty: "Relative novelty",
};

export function RunReport({
  report,
  locale = "en",
}: {
  report: PipelineReport;
  locale?: Locale;
}) {
  const [tab, setTab] = useState("overview");
  const papers = report.papers || [];
  const byId = Object.fromEntries(papers.map((p) => [p.paper_id, p]));
  const critiques = report.critiques || [];
  const supported = critiques.filter((c) => c.status === "supported");
  const verified = (report.validation_report || []).filter((v) => v.status === "verified");

  const tabs = [
    { id: "overview", label: t(locale, "overview") },
    { id: "papers", label: t(locale, "papers") },
    { id: "critiques", label: t(locale, "critiques") },
    { id: "outline", label: t(locale, "outline") },
    { id: "citations", label: t(locale, "citations") },
  ];

  function downloadJson() {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `athena_report_${report.run_id || "run"}.json`;
    a.click();
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 border-b border-surface pb-2">
        {tabs.map((tb) => (
          <button
            key={tb.id}
            type="button"
            onClick={() => setTab(tb.id)}
            className={`rounded px-3 py-1.5 text-sm ${
              tab === tb.id ? "bg-primary text-white" : "bg-surface hover:opacity-80"
            }`}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card><p className="text-xs text-foreground/60">Papers</p><p className="text-2xl font-bold">{papers.length}</p></Card>
          <Card><p className="text-xs text-foreground/60">Critiques</p><p className="text-2xl font-bold">{supported.length}</p></Card>
          <Card><p className="text-xs text-foreground/60">Citations verified</p><p className="text-2xl font-bold">{verified.length}/{(report.validation_report||[]).length}</p></Card>
          <Card><p className="text-xs text-foreground/60">Grounding</p><p className="text-2xl font-bold">{report.critic_meta?.evidence_grounding_rate != null ? `${Math.round(report.critic_meta.evidence_grounding_rate*100)}%` : "—"}</p></Card>
          {(report.research_errors||[]).length > 0 && (
            <div className="col-span-full rounded bg-mismatch/50 p-3 text-sm">
              {(report.research_errors||[]).map((e) => <p key={e}>• {e}</p>)}
            </div>
          )}
        </div>
      )}

      {tab === "papers" && (
        <div className="space-y-3">
          {papers.map((p) => (
            <Card key={p.paper_id}><PaperCard paper={p} /></Card>
          ))}
        </div>
      )}

      {tab === "critiques" && (
        <div className="space-y-3">
          {critiques.map((c, i) => (
            <Card key={i}>
              <p className="text-xs font-medium text-primary">{CRITIQUE_LABELS[c.type||""] || c.type}</p>
              <p className="mt-1 text-sm">{c.claim}</p>
              <div className="mt-2 space-y-2">
                {(c.evidence_paper_ids||[]).map((pid) => (
                  <div key={pid} className="rounded bg-surface p-2">
                    {byId[pid] ? <PaperCard paper={byId[pid]} /> : <p className="text-xs">{pid}</p>}
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}

      {tab === "outline" && report.draft && (
        <Card>
          <h3 className="text-lg font-semibold">{report.draft.title}</h3>
          {(report.draft.sections||[]).map((sec, i) => (
            <div key={i} className="mt-4">
              <h4 className="font-medium">{sec.heading}</h4>
              <ul className="mt-1 list-disc pl-5 text-sm">
                {(sec.bullets||[]).map((b, j) => <li key={j}>{b}</li>)}
              </ul>
            </div>
          ))}
        </Card>
      )}

      {tab === "citations" && (
        <div className="space-y-2">
          {(report.validation_report||[]).map((vr, i) => (
            <Card key={i} className="flex items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium">{(vr.citation as {title?:string})?.title || `Citation ${i+1}`}</p>
                {vr.matched_doi && <p className="text-xs">DOI: {vr.matched_doi}</p>}
              </div>
              <CitationBadge status={vr.status} />
            </Card>
          ))}
        </div>
      )}

      <Button type="button" variant="outline" onClick={downloadJson}>{t(locale, "downloadJson")}</Button>
    </div>
  );
}
