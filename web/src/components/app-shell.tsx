"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import { Menu } from "lucide-react";
import { IntegrityBanner } from "./integrity-banner";
import { cn } from "@/lib/utils";
import { t, type Locale } from "@/lib/i18n";
import { ensureApiToken } from "@/lib/api-token";
import { setStoredToken } from "@/lib/token-storage";

const NAV = [
  { href: "/app", key: "workspace" as const },
  { href: "/app/library", key: "library" as const },
  { href: "/app/history", key: "history" as const },
  { href: "/profile", key: "profile" as const },
];

export function AppShell({
  children,
  locale = "en",
}: {
  children: React.ReactNode;
  locale?: Locale;
}) {
  const pathname = usePathname();
  const { data: session } = useSession();
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (session?.user?.email) void ensureApiToken();
  }, [session?.user?.email]);

  const sidebar = (
    <nav className="flex flex-col gap-1 p-4">
      <p className="mb-4 text-lg font-bold text-primary">{t(locale, "appName")}</p>
      {NAV.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          prefetch
          onClick={() => setOpen(false)}
          className={cn(
            "rounded px-3 py-2 text-sm font-medium transition-colors",
            pathname === item.href || pathname.startsWith(item.href + "/")
              ? "bg-white text-primary shadow-sm"
              : "text-foreground/80 hover:bg-white/60",
          )}
        >
          {t(locale, item.key)}
        </Link>
      ))}
      <Link
        href="/settings"
        prefetch
        className="mt-4 rounded px-3 py-2 text-sm hover:bg-white/60"
      >
        {t(locale, "settings")}
      </Link>
    </nav>
  );

  return (
    <div className="min-h-screen bg-background">
      <div className="flex">
        <aside className="hidden w-56 shrink-0 bg-surface md:block">{sidebar}</aside>
        {open && (
          <div className="fixed inset-0 z-40 md:hidden">
            <div className="absolute inset-0 bg-black/30" onClick={() => setOpen(false)} />
            <aside className="relative z-50 h-full w-64 bg-surface shadow-lg">{sidebar}</aside>
          </div>
        )}
        <div className="flex min-h-screen flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-surface bg-white px-4 py-3">
            <button
              type="button"
              className="md:hidden"
              aria-label="Open menu"
              onClick={() => setOpen(true)}
            >
              <Menu className="h-6 w-6" />
            </button>
            <div className="flex items-center gap-3">
              {session?.user?.image && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={session.user.image} alt="" className="h-8 w-8 rounded-full" />
              )}
              <span className="text-sm">{session?.user?.name || session?.user?.email}</span>
              <button
                type="button"
                className="text-sm text-primary"
                onClick={() => {
                  setStoredToken(null);
                  signOut({ callbackUrl: "/" });
                }}
              >
                {t(locale, "logout")}
              </button>
            </div>
          </header>
          <main className="flex-1 space-y-4 p-4 md:p-6">
            <IntegrityBanner locale={locale} />
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
