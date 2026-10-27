import type { MatchResult, RankResult } from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "";

async function post<T>(path: string, body: FormData): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, { method: "POST", body });
  } catch {
    throw new Error("Couldn't reach the server. Is the backend running?");
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") msg = data.detail;
    } catch {
      // not JSON, keep the generic message
    }
    throw new Error(msg);
  }
  return res.json();
}

export function matchResume(jd: string, resume: File | string): Promise<MatchResult> {
  const form = new FormData();
  form.append("jd_text", jd);
  if (typeof resume === "string") form.append("resume_text", resume);
  else form.append("resume", resume);
  return post("/api/match", form);
}

export function rankResumes(jd: string, files: File[]): Promise<RankResult> {
  const form = new FormData();
  form.append("jd_text", jd);
  files.forEach((f) => form.append("resumes", f));
  return post("/api/rank", form);
}
