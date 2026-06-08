import { getServerSession } from "next-auth";
import { NextResponse } from "next/server";
import { authOptions } from "@/lib/auth-options";
import { syncApiToken } from "@/lib/sync-api-token";

export async function GET() {
  const session = await getServerSession(authOptions);
  if (!session?.user?.email) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const user = session.user;
  const accessToken = await syncApiToken({
    sub: user.id || user.email!,
    email: user.email!,
    display_name: user.name,
    avatar_url: user.image,
  });
  if (!accessToken) {
    return NextResponse.json({ error: "API sync failed" }, { status: 500 });
  }
  return NextResponse.json({ access_token: accessToken });
}
