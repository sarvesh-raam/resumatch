"""Score a resume against a job description and explain the gaps.

The score is a weighted average of per-requirement coverage:

  - every JD line becomes a requirement (must / duty / nice, see jd.py)
  - each requirement is compared with every resume line by cosine similarity
  - if the requirement names skills, whether those skills appear in the
    resume counts for most of its coverage; similarity covers the rest.
    Similarity alone is too forgiving here, "Kubernetes" and "Docker" lines
    embed close together but they aren't the same skill.
"""

from __future__ import annotations

import numpy as np

from .embedding import Embedder
from .jd import MUST, NICE, ParsedJD, parse_jd
from .resume import EVIDENCE_SECTIONS, ParsedResume, evidence_lines, parse_resume
from .schemas import Evidence, MatchResult, RequirementResult, SkillResult
from .skills import SkillIndex

SKILL_WEIGHT = 0.7
# A skill that only appears in the skills list gets a little credit, not much.
# Anyone can type "Kubernetes" into a list; the eval's keyword-stuffed resume
# ranked second for most JDs when this was 0.75.
CREDIT = {"demonstrated": 1.0, "implied": 0.5, "listed": 0.35, "missing": 0.0}
SKILLS_SECTION_PENALTY = 0.05
SKILL_MENTION_BONUS = 0.1

COVERED, PARTIAL = 0.7, 0.35


class NoRequirements(ValueError):
    pass


class JobMatcher:
    """Holds a parsed JD and its embeddings so many resumes can be scored cheaply."""

    def __init__(self, jd_text: str, embedder: Embedder, skills: SkillIndex):
        self.embedder = embedder
        self.skills = skills
        self.jd: ParsedJD = parse_jd(jd_text, skills)
        if not self.jd.requirements:
            raise NoRequirements(
                "Couldn't find any requirements in the job description. "
                "Paste the full posting, including the requirements/qualifications part."
            )
        self.req_vecs = embedder.encode([r.text for r in self.jd.requirements])
        self.skill_kinds = self.jd.skill_kinds()

    def score_text(self, resume_text: str) -> MatchResult:
        return self.score(parse_resume(resume_text))

    def score(self, resume: ParsedResume) -> MatchResult:
        lines = evidence_lines(resume)
        statuses, notes = self._skill_status(resume)

        if lines:
            line_vecs = self.embedder.encode([l.text for l in lines])
            sims = self.req_vecs @ line_vecs.T  # (n_reqs, n_lines), vectors are normalised
            line_skills = [self.skills.find(l.text) for l in lines]
            penalty = np.array([SKILLS_SECTION_PENALTY if l.section == "skills" else 0.0 for l in lines])
        else:
            sims = np.zeros((len(self.jd.requirements), 0))

        results = []
        for i, req in enumerate(self.jd.requirements):
            evidence, sim = None, 0.0
            if sims.shape[1]:
                ranked = sims[i] - penalty
                if req.skills:
                    ranked = ranked + np.array([SKILL_MENTION_BONUS if req.skills & ls else 0.0 for ls in line_skills])
                j = int(np.argmax(ranked))
                sim = float(sims[i, j])
                evidence = Evidence(text=lines[j].text, section=lines[j].section, similarity=round(sim, 3))

            sem = self._semantic_coverage(sim)
            found = sorted(s for s in req.skills if statuses[s] != "missing")
            missing = sorted(s for g in req.groups if all(statuses[x] == "missing" for x in g) for s in g)
            if req.groups:
                skill_cov = sum(max(CREDIT[statuses[s]] for s in g) for g in req.groups) / len(req.groups)
                coverage = SKILL_WEIGHT * skill_cov + (1 - SKILL_WEIGHT) * sem
            else:
                coverage = sem

            if sem == 0 and not found:
                evidence = None  # nothing close enough to be worth showing

            status = "covered" if coverage >= COVERED else "partial" if coverage >= PARTIAL else "missing"
            if status == "missing" and found:
                status = "partial"  # don't call it missing while showing a skill as found
            results.append(
                RequirementResult(
                    text=req.text,
                    kind=req.kind,
                    status=status,
                    coverage=round(coverage, 3),
                    skills_found=found,
                    skills_missing=missing,
                    evidence=evidence,
                )
            )

        total_w = sum(r.weight for r in self.jd.requirements)
        score = sum(r.weight * res.coverage for r, res in zip(self.jd.requirements, results)) / total_w

        must = [res for res in results if res.kind == MUST]
        must_cov = round(sum(r.coverage for r in must) / len(must), 3) if must else None

        self._note_alternatives(statuses, notes)
        skill_results = self._skill_results(statuses, notes)
        gaps = self._gaps(skill_results)
        return MatchResult(
            score=round(score * 100),
            must_coverage=must_cov,
            missing_must=gaps[MUST],
            summary=self._summary(results, skill_results, gaps),
            requirements=results,
            skills=skill_results,
            resume_sections=resume.sections,
            experience_notes=self.jd.years,
            embedder=self.embedder.name,
        )

    def _semantic_coverage(self, sim: float) -> float:
        e = self.embedder
        return float(np.clip((sim - e.weak) / (e.strong - e.weak), 0.0, 1.0))

    def _skill_status(self, resume: ParsedResume) -> tuple[dict[str, str], dict[str, str]]:
        shown = self.skills.find(resume.section_text(*EVIDENCE_SECTIONS))
        anywhere = self.skills.find(resume.full_text)
        implied_shown = self.skills.implied_by(shown)
        implied_listed = self.skills.implied_by(anywhere)

        # Order matters: using PyTorch in a project says more about Python than
        # having "Python" in the skills list does.
        statuses, notes = {}, {}
        for skill in self.skill_kinds:
            if skill in shown:
                statuses[skill] = "demonstrated"
            elif skill in implied_shown:
                statuses[skill] = "implied"
                notes[skill] = f"Not named in a project or job, but implied by {implied_shown[skill]}, which is."
            elif skill in anywhere:
                statuses[skill] = "listed"
                notes[skill] = "Listed, but no project or experience line mentions it."
            elif skill in implied_listed:
                statuses[skill] = "listed"
                notes[skill] = f"Not named. Implied by {implied_listed[skill]}, but that's only listed too."
            else:
                statuses[skill] = "missing"
        return statuses, notes

    def _note_alternatives(self, statuses: dict[str, str], notes: dict[str, str]) -> None:
        """Handle skills the JD only asks for as one of several options.

        If the JD says "FastAPI or Django" and the resume shows FastAPI, Django
        isn't a gap, whether it's missing or only listed. A skill is hidden
        (status None) when every group it appears in has another option the
        resume backs up better.
        """
        rank = {"missing": 0, "listed": 1, "implied": 2, "demonstrated": 3}
        before = dict(statuses)  # decide from the original statuses, not half-updated ones
        groups_of: dict[str, list[set[str]]] = {}
        for req in self.jd.requirements:
            for g in req.groups:
                for s in g:
                    groups_of.setdefault(s, []).append(g)

        for skill, groups in groups_of.items():
            mine = rank[before[skill]]
            if all(any(rank[before[x]] > mine for x in g if x != skill) for g in groups):
                statuses[skill] = None
                continue
            if before[skill] == "missing":
                open_groups = [g for g in groups if all(before[x] == "missing" for x in g)]
                if open_groups and all(len(g) > 1 for g in open_groups):
                    others = sorted(set().union(*open_groups) - {skill})
                    notes[skill] = "Any one of " + ", ".join([skill, *others]) + " would do."

    def _skill_results(self, statuses: dict[str, str | None], notes: dict[str, str]) -> list[SkillResult]:
        order = {MUST: 0, "duty": 1, NICE: 2}
        status_order = {"missing": 0, "listed": 1, "implied": 2, "demonstrated": 3}
        out = [
            SkillResult(name=s, kind=k, status=statuses[s], note=notes.get(s))
            for s, k in self.skill_kinds.items()
            if statuses[s] is not None
        ]
        out.sort(key=lambda r: (order[r.kind], status_order[r.status], r.name.lower()))
        return out

    def _gaps(self, skills: list[SkillResult]) -> dict[str, list[str]]:
        """Missing skill groups as readable labels ("Django or FastAPI"), must-haves separate."""
        missing = {s.name for s in skills if s.status == "missing"}
        gaps: dict[str, list[str]] = {MUST: [], "other": []}
        # must-haves first, so a skill that's both must and nice is reported once, as must
        for req in sorted(self.jd.requirements, key=lambda r: r.kind != MUST):
            for g in req.groups:
                if g <= missing:
                    label = " or ".join(sorted(g))
                    bucket = gaps[MUST if req.kind == MUST else "other"]
                    if label not in bucket and label not in gaps[MUST]:
                        bucket.append(label)
        return gaps

    def _summary(
        self, results: list[RequirementResult], skills: list[SkillResult], gaps: dict[str, list[str]]
    ) -> list[str]:
        lines = []
        must = [r for r in results if r.kind == MUST]
        if must:
            covered = sum(r.status == "covered" for r in must)
            partial = sum(r.status == "partial" for r in must)
            s = f"Covers {covered} of {len(must)} must-have requirements"
            lines.append(s + (f", {partial} partly." if partial else "."))

        if gaps[MUST]:
            lines.append("Missing must-have skills: " + ", ".join(gaps[MUST]) + ".")
        if gaps["other"]:
            lines.append("Also not found: " + ", ".join(gaps["other"]) + ".")

        listed = [s.name for s in skills if s.status == "listed"]
        if listed:
            lines.append(
                "Only in the skills list, never shown in a project or job: "
                + ", ".join(listed)
                + ". A bullet that uses them would carry more weight."
            )

        if not lines:
            lines.append("No obvious gaps against this posting.")
        return lines


def match(resume_text: str, jd_text: str, embedder: Embedder, skills: SkillIndex) -> MatchResult:
    return JobMatcher(jd_text, embedder, skills).score(parse_resume(resume_text))
