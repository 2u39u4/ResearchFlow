export type Locale = "en";

const dict = {
  en: {
    appName: "Athena Research Assistant",
    workspace: "Workspace",
    library: "Library",
    history: "History",
    profile: "Profile",
    settings: "Settings",
    login: "Sign in",
    logout: "Sign out",
    getStarted: "Get started",
    continueGoogle: "Continue with Google",
    integrity:
      "Academic integrity — Athena is research assistance only. It does not ghost-write manuscripts or replace author analysis or authorship. Outlines include [TODO: author to complete] markers.",
    startAnalysis: "Start analysis",
    topic: "Research topic",
    yearFrom: "Year from",
    yearTo: "Year to",
    domain: "Domain (optional)",
    minPapers: "Minimum papers",
    perSource: "Max per source",
    overview: "Overview",
    papers: "Papers",
    critiques: "Critiques",
    outline: "Outline",
    citations: "Citations",
    loadDemo: "Load demo report",
    downloadJson: "Download report JSON",
    uploadPdfs: "Upload PDFs (up to five)",
    searchPdfs: "Search your PDFs",
    deleteAccount: "Delete account",
    help: "Help",
  },
} as const;

export function t(_locale: Locale, key: keyof (typeof dict)["en"]): string {
  return dict.en[key];
}
