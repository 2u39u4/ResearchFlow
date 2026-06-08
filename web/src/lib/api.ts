"use client";

import type {
  LibraryHit,
  PipelineReport,
  RunSummary,
  User,
} from "./api-types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("athena_token");
}

export function setStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem("athena_token", token);
  else localStorage.removeItem("athena_token");
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  token?: string | null,
): Promise<T> {
  const auth = token ?? getStoredToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (auth) headers.Authorization = `Bearer ${auth}`;
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function syncGoogleUser(payload: {
  sub: string;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
  locale?: string;
}): Promise<{ access_token: string; user: User }> {
  const secret = process.env.NEXT_PUBLIC_API_SYNC_SECRET || "dev-sync-secret";
  const res = await fetch(`${API_URL}/auth/google`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Sync-Secret": secret,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export const api = {
  me: () => apiFetch<User>("/users/me"),
  updateMe: (body: Partial<User>) =>
    apiFetch<User>("/users/me", { method: "PATCH", body: JSON.stringify(body) }),
  deleteMe: () => apiFetch<{ status: string }>("/users/me", { method: "DELETE" }),

  createRun: (topic: string, constraints: Record<string, unknown>) =>
    apiFetch<{ id: string; status: string }>("/runs", {
      method: "POST",
      body: JSON.stringify({ topic, constraints }),
    }),
  listRuns: () => apiFetch<{ runs: RunSummary[] }>("/runs"),
  getRun: (id: string) =>
    apiFetch<{
      id: string;
      status: string;
      topic: string;
      report?: PipelineReport;
      error_message?: string;
      paper_count?: number;
    }>(`/runs/${id}`),
  deleteRun: (id: string) =>
    apiFetch<{ status: string }>(`/runs/${id}`, { method: "DELETE" }),

  listPdfs: () =>
    apiFetch<{
      docs: unknown[];
      doc_ids: string[];
      chunk_count: number;
      max_docs: number;
      slots_remaining: number;
    }>("/library/pdfs"),
  uploadPdfs: (files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    return apiFetch<{ results: unknown[]; library: unknown }>("/library/pdfs", {
      method: "POST",
      body: fd,
    });
  },
  searchPdfs: (query: string, top_k = 5) =>
    apiFetch<{ hits: LibraryHit[] }>("/library/search", {
      method: "POST",
      body: JSON.stringify({ query, top_k }),
    }),
  deletePdf: (docId: string) =>
    apiFetch<{ status: string }>(`/library/pdfs/${encodeURIComponent(docId)}`, {
      method: "DELETE",
    }),
};

export function subscribeRunEvents(
  runId: string,
  onEvent: (data: { step: string; status: string; detail?: string }) => void,
  onDone: (status: string) => void,
): () => void {
  const token = getStoredToken();
  const url = `${API_URL}/runs/${runId}/events`;
  const controller = new AbortController();

  (async () => {
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: controller.signal,
    });
    if (!res.body) return;
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split("\n\n");
      buffer = parts.pop() || "";
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data:")) continue;
        try {
          const data = JSON.parse(line.slice(5).trim());
          if (data.step === "done") onDone(data.status);
          else onEvent(data);
        } catch {
          /* ignore */
        }
      }
    }
  })().catch(() => {});

  return () => controller.abort();
}
