"""Split a pasted job description into weighted requirement lines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .resume import BULLET_RE
from .skills import SkillIndex

MUST, DUTY, NICE = "must", "duty", "nice"
WEIGHTS = {MUST: 1.0, DUTY: 0.6, NICE: 0.35}

# Checked in this order, first hit wins. "preferred qualifications" has to be
# caught as NICE before the generic "qualification" rule sees it.
_HEADING_RULES: list[tuple[str, str | None]] = [
    (r"nice to have|good to have|preferred|bonus|desired|a plus|pluses|extra credit", NICE),
    (
        r"about (us|the company|the team)|benefits|perks|what we offer|compensation|salary|"
        r"equal opportunity|how to apply|why join|our culture|location|apply now",
        None,
    ),
    (
        r"requirement|required|qualification|must have|must-have|what you bring|what we.re looking for|"
        r"who you are|you have|you.ll need|skills|eligibility|criteria",
        MUST,
    ),
    (
        r"responsibilit|what you.ll do|what you will do|the role|role overview|day to day|"
        r"you will|your work|job description|what you.ll work on",
        DUTY,
    ),
]

_NICE_CUES = re.compile(r"nice to have|good to have|preferred|is a plus|\ba plus\b|bonus|desirable|ideally", re.I)
_MUST_CUES = re.compile(
    r"\bmust\b|\brequired\b|mandatory|strong (experience|knowledge|proficiency|understanding)", re.I
)
_YEARS_RE = re.compile(r"(\d+)\s*\+?\s*(?:-|to|–)?\s*(\d+)?\s*\+?\s*years?", re.I)


@dataclass
class Requirement:
    text: str
    kind: str
    # alternatives: each group is satisfied by any one of its skills
    groups: list[set[str]] = field(default_factory=list)

    @property
    def skills(self) -> set[str]:
        return set().union(*self.groups) if self.groups else set()

    @property
    def weight(self) -> float:
        return WEIGHTS[self.kind]


@dataclass
class ParsedJD:
    requirements: list[Requirement]
    years: list[str] = field(default_factory=list)

    def skill_kinds(self) -> dict[str, str]:
        """Each skill mapped to the most important kind it appears under."""
        rank = {MUST: 0, DUTY: 1, NICE: 2}
        out: dict[str, str] = {}
        for r in self.requirements:
            for s in r.skills:
                if s not in out or rank[r.kind] < rank[out[s]]:
                    out[s] = r.kind
        return out


def _heading_kind(line: str, has_skills: bool) -> tuple[bool, str | None]:
    """(is_heading, kind). kind None means 'ignore this block'."""
    stripped = line.strip().rstrip(":").strip()
    words = stripped.split()
    # "Strong Python skills" is short and mentions skills, but it's a
    # requirement, not a heading. Lines naming an actual skill never count.
    looks_like_heading = (line.strip().endswith(":") and len(words) <= 8) or (
        len(words) <= 5 and not has_skills and not stripped.endswith(".") and not BULLET_RE.match(line)
    )
    if not looks_like_heading:
        return False, None
    low = stripped.lower()
    for pattern, kind in _HEADING_RULES:
        if re.search(pattern, low):
            return True, kind
    return False, None


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?;])\s+(?=[A-Z])", text)
    return [p.strip() for p in parts if p.strip()]


def parse_jd(text: str, skills: SkillIndex) -> ParsedJD:
    kind: str | None = DUTY
    in_section = False
    reqs: list[Requirement] = []
    years: list[str] = []

    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue

        is_heading, heading_kind = _heading_kind(raw, bool(skills.find(raw)))
        if is_heading:
            kind, in_section = heading_kind, True
            continue
        if kind is None:
            continue

        body = BULLET_RE.sub("", raw).strip()
        for sent in _sentences(body):
            found = skills.find(sent)
            # Before the first heading there's usually a job title and an intro
            # paragraph. Skip the title, and keep intro sentences only if they
            # name a skill.
            if not in_section and (not found or len(sent.split()) <= 6):
                continue
            if len(sent.split()) < 3 and not found:
                continue

            this_kind = kind
            if _NICE_CUES.search(sent):
                this_kind = NICE
            elif _MUST_CUES.search(sent):
                this_kind = MUST

            if _YEARS_RE.search(sent):
                years.append(sent)
                # "3+ years of backend experience" can't be checked from a
                # resume reliably, so it's reported rather than scored.
                if not found:
                    continue

            reqs.append(Requirement(sent, this_kind, skills.groups(sent)))

    return ParsedJD(reqs, years)
