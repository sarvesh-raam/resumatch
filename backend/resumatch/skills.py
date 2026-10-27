from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

SKILLS_FILE = Path(__file__).parent / "data" / "skills.yaml"

# Characters that count as "part of the word" around an alias. Without + and #
# in here, "C" would match inside "C++" and "C#". "&" stops "R" matching "R&D".
_BEFORE = r"(?<![A-Za-z0-9+#.])"
_AFTER = r"(?![A-Za-z0-9+#&])"
# One- and two-letter names also can't be followed by a hyphen ("Go-kart").
_AFTER_SHORT = r"(?![A-Za-z0-9+#&\-])"


@dataclass
class Skill:
    name: str
    category: str
    aliases: list[str]
    implies: list[str] = field(default_factory=list)


class SkillIndex:
    def __init__(self, skills: list[Skill]):
        self.skills = {s.name: s for s in skills}
        self._patterns: list[tuple[re.Pattern, str]] = []
        for s in skills:
            for alias in s.aliases:
                body = r"[\s\-]+".join(re.escape(part) for part in alias.split())
                flags = 0 if alias != alias.lower() else re.IGNORECASE
                after = _AFTER_SHORT if len(alias) <= 2 else _AFTER
                self._patterns.append((re.compile(_BEFORE + body + after, flags), s.name))

    def find(self, text: str) -> set[str]:
        return {name for pat, name in self._patterns if pat.search(text)}

    def spans(self, text: str) -> list[tuple[int, int, str]]:
        """Skill mentions in reading order, overlapping matches resolved to the longest."""
        hits = [(m.start(), m.end(), name) for pat, name in self._patterns for m in pat.finditer(text)]
        hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
        out: list[tuple[int, int, str]] = []
        for h in hits:
            if out and h[0] < out[-1][1]:
                continue
            out.append(h)
        return out

    def groups(self, text: str) -> list[set[str]]:
        """Skills in a requirement, grouped into alternatives.

        "Python and FastAPI or Django" -> [{Python}, {FastAPI, Django}]
        "Kafka, RabbitMQ, or SQS"     -> [{Kafka, RabbitMQ, SQS}]
        "Python, SQL and Docker"       -> [{Python}, {SQL}, {Docker}]

        Each group is satisfied by any one of its skills.
        """
        spans = self.spans(text)
        if not spans:
            return []
        runs: list[list[str]] = [[spans[0][2]]]
        has_or = [False]
        for prev, cur in zip(spans, spans[1:]):
            gap = text[prev[1] : cur[0]].strip().lower()
            if gap in {"", ",", "/", "or", ", or", "|"} or gap.endswith((" or", "/")):
                runs[-1].append(cur[2])
                has_or[-1] = has_or[-1] or "or" in gap or "/" in gap
            else:
                runs.append([cur[2]])
                has_or.append(False)

        out: list[set[str]] = []
        for run, alt in zip(runs, has_or):
            if alt:
                out.append(set(run))
            else:
                out.extend({s} for s in run)
        # same skill mentioned twice shouldn't count twice
        seen, deduped = set(), []
        for g in out:
            key = frozenset(g)
            if key not in seen:
                seen.add(key)
                deduped.append(g)
        return deduped

    def implied_by(self, found: set[str]) -> dict[str, str]:
        """Skills not in `found` that follow from ones that are.

        Returns {implied skill: skill that implies it}. Follows chains, so
        Next.js -> React -> JavaScript works.
        """
        implied: dict[str, str] = {}
        frontier = list(found)
        while frontier:
            src = frontier.pop()
            for target in self.skills[src].implies:
                if target not in found and target not in implied:
                    implied[target] = src
                    frontier.append(target)
        return implied


def load_skills(path: Path = SKILLS_FILE) -> list[Skill]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    skills = []
    for category, entries in raw.items():
        for e in entries:
            skills.append(
                Skill(
                    name=e["name"],
                    category=category,
                    aliases=[str(a) for a in e["aliases"]],
                    implies=e.get("implies", []),
                )
            )
    known = {s.name for s in skills}
    for s in skills:
        bad = [i for i in s.implies if i not in known]
        if bad:
            raise ValueError(f"{s.name} implies unknown skill(s): {bad}")
    return skills


@lru_cache(maxsize=1)
def default_index() -> SkillIndex:
    return SkillIndex(load_skills())
