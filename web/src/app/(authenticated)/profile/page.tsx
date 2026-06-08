"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { User } from "@/lib/api-types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function ProfilePage() {
  const [user, setUser] = useState<User | null>(null);
  const [name, setName] = useState("");

  useEffect(() => {
    api.me().then((u) => {
      setUser(u);
      setName(u.display_name || "");
    }).catch(() => toast.error("Failed to load profile"));
  }, []);

  async function save() {
    try {
      const u = await api.updateMe({ display_name: name });
      setUser(u);
      toast.success("Saved");
    } catch {
      toast.error("Failed to save");
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-2xl font-bold">Profile</h1>
      <Card className="space-y-4">
        {user?.avatar_url && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={user.avatar_url} alt="" className="h-16 w-16 rounded-full" />
        )}
        <div>
          <label className="text-xs text-foreground/60">Email (read-only)</label>
          <p className="text-sm">{user?.email}</p>
        </div>
        <div>
          <label className="text-xs text-foreground/60">Display name</label>
          <input
            className="mt-1 w-full rounded border border-surface bg-white px-3 py-2 text-sm"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <Button type="button" onClick={save}>Save</Button>
      </Card>
    </div>
  );
}
