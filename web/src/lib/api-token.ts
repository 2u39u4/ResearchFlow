import { getStoredToken, setStoredToken } from "./token-storage";

let inflight: Promise<string | null> | null = null;

/** Fetch FastAPI JWT once per session; deduplicates concurrent callers. */
export function ensureApiToken(): Promise<string | null> {
  const cached = getStoredToken();
  if (cached) return Promise.resolve(cached);

  if (!inflight) {
    inflight = fetch("/api/auth/athena-token", {
      signal: AbortSignal.timeout(5000),
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { access_token?: string } | null) => {
        const token = data?.access_token ?? null;
        if (token) setStoredToken(token);
        return token;
      })
      .catch(() => null)
      .finally(() => {
        inflight = null;
      });
  }
  return inflight;
}
