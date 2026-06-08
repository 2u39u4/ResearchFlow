import { getServerSession } from "next-auth";
import { NextResponse } from "next/server";
import { authOptions } from "@/lib/auth-options";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const SYNC_SECRET = process.env.API_SYNC_SECRET || "dev-sync-secret";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }
  const user = session.user as { id?: string; email?: string; name?: string; image?: string };
  const res = await fetch(`${API_URL}/auth/google`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Sync-Secret": SYNC_SECRET,
    },
    body: JSON.stringify({
      sub: user.id || user.email,
      email: user.email,
      display_name: user.name,
      avatar_url: user.image,
      locale: "en",
    }),
  });
  if (!res.ok) {
    return NextResponse.json({ error: await res.text() }, { status: 500 });
  }
  const data = await res.json();
  return NextResponse.json(data);
}
