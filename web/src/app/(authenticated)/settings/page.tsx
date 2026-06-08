"use client";

import { signOut } from "next-auth/react";
import { api, setStoredToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { toast } from "sonner";

export default function SettingsPage() {
  async function deleteAccount() {
    if (!confirm("Delete your account? This cannot be undone.")) return;
    try {
      await api.deleteMe();
      setStoredToken(null);
      signOut({ callbackUrl: "/" });
    } catch {
      toast.error("Failed to delete account");
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-2xl font-bold">Settings</h1>
      <Card className="space-y-4">
        <Button
          type="button"
          variant="outline"
          onClick={() => {
            setStoredToken(null);
            signOut({ callbackUrl: "/" });
          }}
        >
          Sign out
        </Button>
        <Button type="button" className="bg-red-600" onClick={deleteAccount}>
          Delete account
        </Button>
      </Card>
    </div>
  );
}
