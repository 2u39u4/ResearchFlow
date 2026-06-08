import type { Paper } from "@/lib/api-types";

export function PaperCard({ paper }: { paper: Paper }) {
  const authors = (paper.authors || []).join(", ").slice(0, 120);
  const abstract = paper.abstract
    ? paper.abstract.length > 400
      ? paper.abstract.slice(0, 397) + "..."
      : paper.abstract
    : "";
  return (
    <div className="space-y-1 text-sm">
      <p className="font-semibold">{paper.title || "Untitled"}</p>
      <p className="text-xs text-foreground/70">
        {[paper.year, paper.venue, paper.doi ? `DOI: ${paper.doi}` : ""]
          .filter(Boolean)
          .join(" · ")}
      </p>
      {authors && <p className="text-xs text-foreground/60">{authors}</p>}
      {abstract && <p className="text-xs leading-relaxed">{abstract}</p>}
    </div>
  );
}
