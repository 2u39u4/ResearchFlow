const STYLES: Record<string, { icon: string; label: string; bg: string }> = {
  verified: { icon: "✅", label: "Verified", bg: "bg-verified" },
  not_found: { icon: "❌", label: "Not found", bg: "bg-not-found" },
  mismatch: { icon: "⚠️", label: "Mismatch", bg: "bg-mismatch" },
};

export function CitationBadge({ status }: { status: string }) {
  const s = STYLES[status] || { icon: "❓", label: status, bg: "bg-surface" };
  return (
    <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium ${s.bg}`}>
      <span aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  );
}
