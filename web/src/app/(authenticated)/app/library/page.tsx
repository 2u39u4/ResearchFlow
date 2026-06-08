"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LibraryHit } from "@/lib/api-types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function LibraryPage() {
  const [info, setInfo] = useState<{
    doc_ids: string[];
    chunk_count: number;
    max_docs: number;
    slots_remaining: number;
  } | null>(null);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<LibraryHit[]>([]);

  function refresh() {
    api.listPdfs().then(setInfo).catch(() => toast.error("Failed to load library"));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function onUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files?.length) return;
    try {
      await api.uploadPdfs(Array.from(files));
      toast.success("Upload complete");
      refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Upload failed");
    }
    e.target.value = "";
  }

  async function onSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    try {
      const res = await api.searchPdfs(query.trim());
      setHits(res.hits);
    } catch {
      toast.error("Search failed");
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <h1 className="text-2xl font-bold">My library</h1>
      <p className="text-sm text-foreground/60">
        Up to five PDFs · stored locally · never sent to scholarly APIs
      </p>
      {info && (
        <Card>
          <p className="text-sm">
            Indexed {info.doc_ids.length}/{info.max_docs} documents · {info.chunk_count} chunks
          </p>
          <ul className="mt-2 text-xs text-foreground/70">
            {info.doc_ids.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </Card>
      )}
      <Card>
        <label className="text-sm font-medium">Upload PDFs (multiple selection)</label>
        <input
          type="file"
          accept=".pdf"
          multiple
          className="mt-2 block w-full text-sm"
          onChange={onUpload}
        />
      </Card>
      <Card>
        <form onSubmit={onSearch} className="flex gap-2">
          <input
            className="flex-1 rounded border border-surface px-3 py-2 text-sm"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search uploaded PDFs…"
          />
          <Button type="submit">Search</Button>
        </form>
        <div className="mt-4 space-y-3">
          {hits.map((h, i) => (
            <div key={i} className="rounded bg-surface p-3 text-sm">
              <p className="text-xs font-medium text-primary">
                #{i + 1} · {h.doc_id} (p.{h.page}) · {h.score.toFixed(3)}
              </p>
              <p className="mt-1 text-xs leading-relaxed">{h.text}</p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
