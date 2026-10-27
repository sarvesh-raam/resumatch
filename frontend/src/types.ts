// Mirrors backend/resumatch/schemas.py

export type Kind = "must" | "duty" | "nice";

export interface Evidence {
  text: string;
  section: string;
  similarity: number;
}

export interface RequirementResult {
  text: string;
  kind: Kind;
  status: "covered" | "partial" | "missing";
  coverage: number;
  skills_found: string[];
  skills_missing: string[];
  evidence: Evidence | null;
}

export interface SkillResult {
  name: string;
  kind: Kind;
  status: "demonstrated" | "listed" | "implied" | "missing";
  note: string | null;
}

export interface MatchResult {
  score: number;
  must_coverage: number | null;
  missing_must: string[];
  summary: string[];
  requirements: RequirementResult[];
  skills: SkillResult[];
  resume_sections: string[];
  experience_notes: string[];
  embedder: string;
}

export interface RankedResume {
  filename: string;
  score: number | null;
  must_coverage: number | null;
  missing_must: string[];
  error: string | null;
  result: MatchResult | null;
}

export interface RankResult {
  candidates: RankedResume[];
  requirement_count: number;
}
