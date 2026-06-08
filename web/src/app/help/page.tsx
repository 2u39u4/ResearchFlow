import Link from "next/link";

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <Link href="/" className="text-sm text-primary">
        &larr; Back to home
      </Link>
      <h1 className="mt-4 text-3xl font-bold">Help &amp; academic integrity</h1>
      <div className="mt-6 space-y-6 text-sm leading-relaxed text-foreground/80">
        <section className="rounded-lg bg-mismatch/40 p-4">
          <h2 className="font-semibold">Academic integrity</h2>
          <p className="mt-2">
            Athena is a research assistance tool. It helps you organize literature, surface gaps, and
            verify citations. It does not produce submission-ready manuscript text and does not
            replace your own analysis, writing, or authorship. Outline sections marked{" "}
            <code>[TODO: author to complete]</code> must be filled in by you.
          </p>
        </section>
        <section>
          <h2 className="font-semibold">PDF privacy</h2>
          <p className="mt-2">
            Uploaded PDFs are stored locally on the server for on-machine semantic search. They are
            never sent to arXiv, Crossref, or other scholarly APIs. Each account may index up to five
            PDFs.
          </p>
        </section>
        <section>
          <h2 className="font-semibold">Data storage</h2>
          <p className="mt-2">
            Analysis runs and account metadata live in a local SQLite database. Deleting your account
            soft-deletes your user record.
          </p>
        </section>
        <section>
          <h2 className="font-semibold">Quick start</h2>
          <p className="mt-2">
            Sign in with Google. Run an analysis from Workspace. Upload PDFs in Library (up to five).
            Your data is isolated per account.
          </p>
        </section>
      </div>
    </div>
  );
}
