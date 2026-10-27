import type { Kind, MatchResult, RequirementResult, SkillResult } from "../types";

const KIND_TITLE: Record<Kind, string> = {
  must: "Must-have",
  duty: "Responsibilities",
  nice: "Nice to have",
};

const SKILL_GROUPS: { status: SkillResult["status"]; title: string; hint: string }[] = [
  { status: "missing", title: "Not found", hint: "The posting asks for these and the resume never mentions them." },
  { status: "listed", title: "Only listed", hint: "In the skills section, but no project or job line uses them." },
  { status: "implied", title: "Implied", hint: "Not named, but follows from something that is." },
  { status: "demonstrated", title: "Shown", hint: "Used in a project or experience line." },
];

function pct(x: number | null) {
  return x == null ? "n/a" : `${Math.round(x * 100)}%`;
}

function scoreLabel(score: number) {
  if (score >= 75) return "Strong match";
  if (score >= 50) return "Decent match";
  if (score >= 30) return "Weak match";
  return "Poor match";
}

export default function ResultPanel({ result }: { result: MatchResult }) {
  const byKind = (k: Kind) => result.requirements.filter((r) => r.kind === k);

  return (
    <section className="result">
      <div className="overview">
        <div className="score" data-band={Math.min(3, Math.floor(result.score / 25))}>
          <span className="num">{result.score}</span>
          <span className="of">/ 100</span>
          <span className="band">{scoreLabel(result.score)}</span>
        </div>
        <div className="summary">
          {result.must_coverage != null && (
            <p className="muted">Must-have coverage: {pct(result.must_coverage)}</p>
          )}
          <ul>
            {result.summary.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          {result.experience_notes.length > 0 && (
            <p className="note">
              Not scored, check these yourself: {result.experience_notes.map((n) => `"${n}"`).join(", ")}
            </p>
          )}
        </div>
      </div>

      {result.skills.length > 0 && (
        <div className="block">
          <h2>Skills the posting mentions</h2>
          <div className="skill-groups">
            {SKILL_GROUPS.map((g) => {
              const items = result.skills.filter((s) => s.status === g.status);
              if (!items.length) return null;
              return (
                <div key={g.status} className="skill-group">
                  <h3 title={g.hint}>
                    {g.title} <span className="count">{items.length}</span>
                  </h3>
                  <div className="chips">
                    {items.map((s) => (
                      <span key={s.name} className={`chip ${s.status}`} title={s.note ?? g.hint}>
                        {s.name}
                        {s.kind === "must" && <em>must</em>}
                      </span>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div className="block">
        <h2>Requirement by requirement</h2>
        {(["must", "duty", "nice"] as Kind[]).map((k) => {
          const reqs = byKind(k);
          if (!reqs.length) return null;
          return (
            <div key={k} className="req-group">
              <h3>{KIND_TITLE[k]}</h3>
              <ol className="reqs">
                {reqs.map((r, i) => (
                  <Requirement key={i} req={r} />
                ))}
              </ol>
            </div>
          );
        })}
      </div>

      <p className="fine">
        Sections found: {result.resume_sections.join(", ") || "none (matched against the whole text)"}. Model:{" "}
        {result.embedder}.
      </p>
    </section>
  );
}

function Requirement({ req }: { req: RequirementResult }) {
  return (
    <li className={`req ${req.status}`}>
      <div className="req-head">
        <span className="status">{req.status}</span>
        <span className="req-text">{req.text}</span>
      </div>
      {req.evidence ? (
        <blockquote>
          {req.evidence.text}
          <cite>
            {req.evidence.section} · similarity {req.evidence.similarity.toFixed(2)}
          </cite>
        </blockquote>
      ) : (
        <p className="no-evidence">Nothing in the resume comes close.</p>
      )}
      {req.skills_missing.length > 0 && (
        <p className="gap">Missing: {req.skills_missing.join(", ")}</p>
      )}
    </li>
  );
}
