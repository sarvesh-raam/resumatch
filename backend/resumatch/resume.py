"""Turn raw resume text into sections and evidence lines."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_ALIASES = {
    "summary": ["summary", "profile", "objective", "about me", "professional summary", "career objective"],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "internships",
        "internship",
        "work history",
    ],
    "projects": ["projects", "personal projects", "academic projects", "key projects", "selected projects"],
    "skills": ["skills", "technical skills", "core skills", "tech stack", "technologies", "skills and tools"],
    "education": ["education", "academic background", "academics"],
    "certifications": ["certifications", "certificates", "licenses and certifications"],
    "achievements": ["achievements", "awards", "honors", "honours", "awards and achievements"],
    "leadership": ["leadership", "activities", "extracurricular", "leadership and activities", "volunteering"],
    "publications": ["publications", "research"],
    "coursework": ["coursework", "relevant coursework"],
}
_HEADINGS = {alias: canon for canon, aliases in SECTION_ALIASES.items() for alias in aliases}

# Sections whose lines count as "shown in practice" rather than just listed.
EVIDENCE_SECTIONS = {"experience", "projects", "summary", "achievements", "leadership", "publications", "other"}

BULLET_RE = re.compile(r"^\s*[•●▪◦‣∙·\-\*–]\s*")
CONTACT_RE = re.compile(r"@|https?://|www\.|linkedin\.com|github\.com|\+?\d[\d\s\-]{8,}\d")
DATE_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}\b|\b(19|20)\d{2}\s*[–\-]\s*((19|20)\d{2}|present)\b",
    re.IGNORECASE,
)


TITLE_DASH_RE = re.compile(r"\s[—–]\s")
HYPHEN_WRAP_RE = re.compile(r"[a-z]-$")


@dataclass
class Line:
    text: str
    section: str


@dataclass
class ParsedResume:
    lines: list[Line]
    sections: list[str] = field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    def section_text(self, *names: str) -> str:
        return "\n".join(l.text for l in self.lines if l.section in names)


def _heading(line: str) -> str | None:
    cleaned = re.sub(r"[^a-z& ]", "", line.lower()).replace("&", "and")
    cleaned = " ".join(cleaned.split())
    if not cleaned or len(cleaned.split()) > 4:
        return None
    if cleaned in _HEADINGS:
        return _HEADINGS[cleaned]
    # "Internship Experience", "Research Experience", "Technical Projects"...
    last = cleaned.split()[-1]
    if len(cleaned.split()) <= 3 and last in _HEADINGS and last != "research":
        return _HEADINGS[last]
    return None


_CONTINUES = (
    ",",
    "(",
    "-",
    "–",
    "/",
    "&",
    " and",
    " with",
    " of",
    " the",
    " to",
    " by",
    " in",
    " for",
    " on",
    " using",
    " from",
    " into",
    " as",
    " a",
    " an",
)
# A PDF line at least this long that ends without punctuation was most likely
# wrapped by the layout rather than ended by the author.
WRAP_LEN = 60


def _starts_new_line(raw: str, prev: str, prev_raw_len: int) -> bool:
    """Decide whether a non-bullet PDF line is a fresh item or a wrapped continuation."""
    if not prev:
        return True
    if DATE_RE.search(raw) or "|" in raw:
        return True  # role/company/date rows
    if TITLE_DASH_RE.search(raw) and len(raw.split()) <= 10:
        return True  # "ARIA — Financial Risk Platform"
    if raw[0].islower():
        return False
    if prev.rstrip().endswith(_CONTINUES):
        return False
    words = raw.split()
    # short Title Case line on its own: probably a job title or project name
    if len(words) <= 6 and sum(w[0].isupper() for w in words if w[0].isalpha()) >= len(words) - 1:
        return True
    if prev.rstrip().endswith((".", "!", "?", ":")):
        return True
    return prev_raw_len < WRAP_LEN


def parse_resume(text: str) -> ParsedResume:
    section = "header"
    seen: list[str] = []
    items: list[Line] = []
    pending_bullet = False
    prev_raw_len = 0

    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue

        if BULLET_RE.sub("", raw) == "":
            # some PDFs put the bullet glyph on its own line
            pending_bullet = True
            continue

        heading = _heading(raw)
        if heading:
            section = heading
            if heading not in seen:
                seen.append(heading)
            pending_bullet = False
            continue

        is_bullet = pending_bullet or bool(BULLET_RE.match(raw))
        pending_bullet = False
        body = BULLET_RE.sub("", raw).strip()

        prev = items[-1] if items and items[-1].section == section else None
        if not is_bullet and prev and not _starts_new_line(body, prev.text, prev_raw_len):
            if HYPHEN_WRAP_RE.search(prev.text) and body[0].islower():
                prev.text = prev.text[:-1] + body  # "visual-" + "ization"
            else:
                prev.text = f"{prev.text} {body}"
        else:
            items.append(Line(body, section))
        prev_raw_len = len(raw)

    if not seen:
        # No recognisable headings (plain text paste, unusual template).
        # Better to match against everything than to drop the whole resume.
        for l in items:
            l.section = "other"

    lines = [l for l in items if _keep(l)]
    return ParsedResume(lines=lines, sections=seen)


def _keep(line: Line) -> bool:
    if line.section == "header":
        return False  # name, contact details, headline
    if CONTACT_RE.search(line.text) and len(line.text.split()) < 8:
        return False
    # skills are often listed one per line, so single words count there
    return line.section == "skills" or len(line.text.split()) >= 2


def evidence_lines(resume: ParsedResume) -> list[Line]:
    """Lines worth comparing against job requirements.

    Drops one-word fragments and pure date/title rows, which only add noise to
    similarity search. Skills-section lines are kept: they're weak evidence but
    still evidence.
    """
    out = []
    for l in resume.lines:
        words = l.text.split()
        if len(words) < 3 and l.section != "skills":
            continue
        # company/role/date rows: short, or laid out with pipes or wide gaps
        if DATE_RE.search(l.text) and (len(words) <= 12 or "|" in l.text or "   " in l.text):
            continue
        out.append(l)
    return out
