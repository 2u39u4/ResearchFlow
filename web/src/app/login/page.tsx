"use client";

import { signIn } from "next-auth/react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <Card className="w-full max-w-md space-y-6 text-center">
        <div>
          <h1 className="text-2xl font-bold text-primary">Athena</h1>
          <p className="mt-2 text-sm text-foreground/70">Sign in to use the research assistant</p>
        </div>
        <Button
          type="button"
          className="w-full py-3"
          onClick={() => signIn("google", { callbackUrl: "/app" })}
        >
          Continue with Google
        </Button>
        <p className="text-xs text-foreground/50">
          By signing in you acknowledge this tool is for research assistance only.{" "}
          <Link href="/help" className="text-primary underline">
            Academic integrity policy
          </Link>
        </p>
      </Card>
    </div>
  );
}
