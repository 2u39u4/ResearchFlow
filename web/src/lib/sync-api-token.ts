/** Exchange Google profile for a FastAPI JWT (server-side only). */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SYNC_SECRET = process.env.API_SYNC_SECRET || "dev-sync-secret";

export async function syncApiToken(payload: {
  sub: string;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
  locale?: string;
}): Promise<string | null> {
  const res = await fetch(`${API_URL}/auth/google`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Sync-Secret": SYNC_SECRET,
    },
    body: JSON.stringify({
      locale: "en",
      ...payload,
    }),
    cache: "no-store",
    signal: AbortSignal.timeout(3000),
  });
  if (!res.ok) return null;
  const data = (await res.json()) as { access_token?: string };
  return data.access_token ?? null;
}
