from typing import Literal

from pydantic import BaseModel

Kind = Literal["must", "duty", "nice"]


class Evidence(BaseModel):
    text: str
    section: str
    similarity: float


class RequirementResult(BaseModel):
    text: str
    kind: Kind
    status: Literal["covered", "partial", "missing"]
    coverage: float
    skills_found: list[str]
    skills_missing: list[str]
    evidence: Evidence | None


class SkillResult(BaseModel):
    name: str
    kind: Kind
    status: Literal["demonstrated", "listed", "implied", "missing"]
    note: str | None = None


class MatchResult(BaseModel):
    score: int
    must_coverage: float | None
    missing_must: list[str]
    summary: list[str]
    requirements: list[RequirementResult]
    skills: list[SkillResult]
    resume_sections: list[str]
    experience_notes: list[str]
    embedder: str


class RankedResume(BaseModel):
    filename: str
    score: int | None
    must_coverage: float | None = None
    missing_must: list[str] = []
    error: str | None = None
    result: MatchResult | None = None


class RankResult(BaseModel):
    candidates: list[RankedResume]
    requirement_count: int
