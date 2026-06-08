"use client";

import { t, type Locale } from "@/lib/i18n";

export function IntegrityBanner({ locale = "en" }: { locale?: Locale }) {
  return (
    <div
      className="rounded-lg border border-mismatch bg-mismatch/60 px-4 py-3 text-sm text-foreground"
      role="note"
      aria-label="Academic integrity notice"
    >
      ⚖️ {t(locale, "integrity")}
    </div>
  );
}
