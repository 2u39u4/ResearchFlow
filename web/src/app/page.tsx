import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-surface px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <span className="text-xl font-bold text-primary">Athena</span>
          <Link href="/login">
            <Button>Get started</Button>
          </Link>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-16">
        <section className="text-center">
          <h1 className="text-4xl font-bold tracking-tight text-foreground md:text-5xl">
            Literature review, evidence-backed
          </h1>
          <p className="mx-auto mt-4 max-w-2xl text-lg text-foreground/70">
            Multi-agent retrieval, evidence-grounded critiques, outline scaffolding, and citation
            verification — a research assistant for scholars, not a ghostwriter.
          </p>
          <div className="mt-8 flex justify-center gap-4">
            <Link href="/login">
              <Button className="px-8 py-3 text-base">Get started</Button>
            </Link>
            <Link href="/help">
              <Button variant="outline" className="px-8 py-3 text-base">
                Learn more
              </Button>
            </Link>
          </div>
        </section>
        <section className="mt-20 grid gap-6 md:grid-cols-3">
          {[
            {
              title: "Workspace",
              desc: "Enter a topic; Athena retrieves papers and builds a structured review scaffold.",
            },
            {
              title: "Citation verification",
              desc: "Every citation is checked against scholarly APIs — green, red, and yellow status at a glance.",
            },
            {
              title: "Private library",
              desc: "Upload up to five PDFs for local semantic search; files never leave your server.",
            },
          ].map((f) => (
            <div key={f.title} className="rounded-lg bg-surface p-6">
              <h3 className="font-semibold text-primary">{f.title}</h3>
              <p className="mt-2 text-sm text-foreground/70">{f.desc}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
