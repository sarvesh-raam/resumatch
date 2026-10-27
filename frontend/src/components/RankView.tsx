import { Fragment, useState } from "react";
import { rankResumes } from "../api";
import type { RankResult } from "../types";
import ResultPanel from "./ResultPanel";

const MAX_FILES = 25;

export default function RankView() {
  const [jd, setJd] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [data, setData] = useState<RankResult | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function pick(list: FileList | null) {
    const chosen = Array.from(list ?? []);
    setError(chosen.length > MAX_FILES ? `Only the first ${MAX_FILES} files will be used.` : "");
    setFiles(chosen.slice(0, MAX_FILES));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setOpen(null);
    try {
      setData(await rankResumes(jd, files));
    } catch (err) {
      setData(null);
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <form className="inputs" onSubmit={submit}>
        <div className="field">
          <label htmlFor="resumes">Resumes</label>
          <label className="drop">
            <input id="resumes" type="file" accept="application/pdf" multiple onChange={(e) => pick(e.target.files)} />
            {files.length ? (
              <strong>
                {files.length} file{files.length > 1 ? "s" : ""} selected
              </strong>
            ) : (
              <span>Choose up to {MAX_FILES} PDFs</span>
            )}
          </label>
          {files.length > 0 && (
            <ul className="file-list">
              {files.map((f) => (
                <li key={f.name}>{f.name}</li>
              ))}
            </ul>
          )}
        </div>

        <div className="field">
          <label htmlFor="jd-rank">Job description</label>
          <textarea id="jd-rank" rows={14} value={jd} onChange={(e) => setJd(e.target.value)} />
        </div>

        <div className="actions">
          <button type="submit" className="primary" disabled={busy || !jd.trim() || !files.length}>
            {busy ? `Scoring ${files.length}...` : "Rank resumes"}
          </button>
          {error && <p className="error">{error}</p>}
        </div>
      </form>

      {data && (
        <section className="result">
          <p className="muted">
            Scored against {data.requirement_count} requirements. Click a row for the full breakdown.
          </p>
          <table className="rank">
            <thead>
              <tr>
                <th>#</th>
                <th>File</th>
                <th>Score</th>
                <th>Must-have</th>
                <th>Missing must-haves</th>
              </tr>
            </thead>
            <tbody>
              {data.candidates.map((c, i) => (
                <Fragment key={c.filename + i}>
                  <tr
                    className={c.error ? "failed" : "clickable"}
                    onClick={() => c.result && setOpen(open === c.filename ? null : c.filename)}
                  >
                    <td>{c.error ? "" : i + 1}</td>
                    <td>{c.filename}</td>
                    <td className="num-cell">{c.score ?? "-"}</td>
                    <td className="num-cell">
                      {c.must_coverage == null ? "-" : `${Math.round(c.must_coverage * 100)}%`}
                    </td>
                    <td>{c.error ? <span className="error">{c.error}</span> : c.missing_must.join(", ") || "none"}</td>
                  </tr>
                  {open === c.filename && c.result && (
                    <tr className="detail">
                      <td colSpan={5}>
                        <ResultPanel result={c.result} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </>
  );
}
