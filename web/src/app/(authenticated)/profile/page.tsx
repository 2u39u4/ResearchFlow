"use client";

import { useEffect, useState } from "react";
import { useSession } from "next-auth/react";
import { api } from "@/lib/api";
import type { User } from "@/lib/api-types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

export default function ProfilePage() {
  const { data: session } = useSession();
  const [user, setUser] = useState<User | null>(null);
  const [name, setName] = useState(session?.user?.name || "");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .me()
      .then((u) => {
        setUser(u);
        setName(u.display_name || session?.user?.name || "");
      })
      .catch(() => toast.error("Failed to load profile"))
      .finally(() => setLoading(false));
  }, [session?.user?.name]);

  async function save() {
    try {
      const u = await api.updateMe({ display_name: name });
      setUser(u);
      toast.success("Saved");
    } catch {
      toast.error("Failed to save");
    }
  }

  const email = user?.email || session?.user?.email || "";
  const avatar = user?.avatar_url || session?.user?.image;

  return (
    <div className="mx-auto max-w-lg space-y-4">
      <h1 className="text-2xl font-bold">Profile</h1>
      <Card className="space-y-4">
        {avatar && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={avatar} alt="" className="h-16 w-16 rounded-full" />
        )}
        <div>
          <label className="text-xs text-foreground/60">Email (read-only)</label>
          <p className="text-sm">{email || (loading ? "Loading…" : "—")}</p>
        </div>
        <div>
          <label className="text-xs text-foreground/60">Display name</label>
          <input
            className="mt-1 w-full rounded border border-surface bg-white px-3 py-2 text-sm"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <Button type="button" onClick={save} disabled={loading}>
          Save
        </Button>
      </Card>
    </div>
  );
}
