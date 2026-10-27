import { useState } from "react";
import { matchResume } from "../api";
import type { MatchResult } from "../types";
import ResultPanel from "./ResultPanel";

export default function MatchView() {
  const [jd, setJd] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [pasted, setPasted] = useState("");
  const [usePaste, setUsePaste] = useState(false);
  const [result, setResult] = useState<MatchResult | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const resume = usePaste ? pasted.trim() : file;
  const ready = jd.trim().length > 0 && !!resume && !busy;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!resume) return;
    setBusy(true);
    setError("");
    try {
      setResult(await matchResume(jd, resume));
    } catch (err) {
      setResult(null);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form className="inputs" onSubmit={submit}>
        <div className="field">
          <div className="label-row">
            <label htmlFor="resume">Resume</label>
            <button type="button" className="link" onClick={() => setUsePaste(!usePaste)}>
              {usePaste ? "Upload a PDF instead" : "Paste text instead"}
            </button>
          </div>
          {usePaste ? (
            <textarea
              id="resume"
              rows={14}
              value={pasted}
              onChange={(e) => setPasted(e.target.value)}
              placeholder="Paste the resume text. Keep the section headings (Experience, Projects, Skills...) if you can."
            />
          ) : (
            <label className="drop">
              <input
                id="resume"
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              />
              {file ? <strong>{file.name}</strong> : <span>Choose a PDF (text-based, up to 5 MB)</span>}
            </label>
          )}
        </div>

        <div className="field">
          <label htmlFor="jd">Job description</label>
          <textarea
            id="jd"
            rows={14}
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            placeholder="Paste the whole posting. Headings like 'Requirements' and 'Nice to have' help it weight things properly."
          />
        </div>

        <div className="actions">
          <button type="submit" className="primary" disabled={!ready}>
            {busy ? "Checking..." : "Check match"}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </form>

      {result && <ResultPanel result={result} />}
    </>
  );
}
