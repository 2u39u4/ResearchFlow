"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex min-h-[50vh] max-w-lg flex-col items-center justify-center gap-4 p-6 text-center">
      <h2 className="text-xl font-bold">Something went wrong</h2>
      <p className="text-sm text-foreground/70">
        {error.message || "Please try again or return to the workspace."}
      </p>
      <Button onClick={reset}>Try again</Button>
    </div>
  );
}
