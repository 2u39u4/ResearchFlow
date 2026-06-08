import { redirect } from "next/navigation";
import { getServerSession } from "next-auth";
import Link from "next/link";
import { cookies } from "next/headers";
import { authOptions } from "@/lib/auth-options";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

async function getCsrfToken(): Promise<string> {
  const base = process.env.NEXTAUTH_URL || "http://localhost:3000";
  const res = await fetch(`${base}/api/auth/csrf`, {
    headers: { cookie: cookies().toString() },
    cache: "no-store",
  });
  if (!res.ok) return "";
  const data = (await res.json()) as { csrfToken?: string };
  return data.csrfToken || "";
}

export default async function LoginPage() {
  const session = await getServerSession(authOptions);
  if (session?.user) redirect("/app");

  const csrfToken = await getCsrfToken();

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <Card className="w-full max-w-md space-y-6 text-center">
        <div>
          <h1 className="text-2xl font-bold text-primary">Athena</h1>
          <p className="mt-2 text-sm text-foreground/70">Sign in to use the research assistant</p>
        </div>
        <form action="/api/auth/signin/google" method="POST" className="w-full">
          <input type="hidden" name="csrfToken" value={csrfToken} />
          <input type="hidden" name="callbackUrl" value="/app" />
          <Button type="submit" className="w-full py-3">
            Continue with Google
          </Button>
        </form>
        <p className="text-xs text-foreground/50">
          First sign-in may take a few seconds while your browser reaches Google.{" "}
          <Link href="/help" className="text-primary underline">
            Academic integrity policy
          </Link>
        </p>
      </Card>
    </div>
  );
}
