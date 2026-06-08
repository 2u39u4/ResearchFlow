export type User = {
  id: string;
  email: string;
  display_name?: string | null;
  avatar_url?: string | null;
  locale?: string;
  default_year_min?: number | null;
  default_year_max?: number | null;
  default_domain?: string | null;
};

export type RunSummary = {
  id: string;
  topic: string;
  status: string;
  paper_count?: number;
  error_message?: string | null;
  created_at: string;
  finished_at?: string | null;
};

export type PipelineReport = {
  run_id?: string;
  topic?: string;
  constraints?: Record<string, unknown>;
  papers?: Paper[];
  critiques?: Critique[];
  draft?: Outline;
  validation_report?: ValidationRow[];
  research_errors?: string[];
  research_sources_ok?: Record<string, boolean>;
  critic_meta?: { evidence_grounding_rate?: number };
  tasks?: unknown[];
  trace?: TraceEntry[];
};

export type Paper = {
  paper_id: string;
  title?: string;
  authors?: string[];
  year?: number;
  venue?: string;
  doi?: string;
  abstract?: string;
};

export type Critique = {
  type?: string;
  claim?: string;
  evidence_paper_ids?: string[];
  confidence?: number;
  status?: string;
  notes?: string;
};

export type Outline = {
  title?: string;
  sections?: { heading?: string; bullets?: string[]; evidence_paper_ids?: string[] }[];
  academic_integrity_note?: string;
};

export type ValidationRow = {
  status: string;
  citation?: Record<string, unknown>;
  matched_title?: string;
  matched_doi?: string;
  match_score?: number;
  details?: Record<string, unknown>;
};

export type TraceEntry = {
  step?: string;
  agent?: string;
  summary?: string;
  created_at?: string;
};

export type LibraryHit = {
  score: number;
  doc_id: string;
  page?: number;
  text: string;
};
