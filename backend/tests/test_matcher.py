import pytest

from resumatch.matcher import JobMatcher, NoRequirements, match

from .conftest import JD, RESUME


@pytest.fixture
def result(embedder, skills):
    return match(RESUME, JD, embedder, skills)


def skill(result, name):
    return next(s for s in result.skills if s.name == name)


def test_score_range(result):
    assert 0 <= result.score <= 100


def test_alternative_satisfied_by_other_option(result):
    # JD says "FastAPI or Django"; resume has FastAPI, so Django isn't a gap
    assert not any(s.name == "Django" for s in result.skills)
    req = next(r for r in result.requirements if "FastAPI or Django" in r.text)
    assert req.skills_missing == []


def test_listed_only_skill(result):
    k8s = skill(result, "Kubernetes")
    assert k8s.status == "listed"
    assert any("Kubernetes" in line and "skills list" in line for line in result.summary)


def test_missing_nice_to_have(result):
    assert skill(result, "Kafka").status == "missing"
    assert skill(result, "Kafka").kind == "nice"


def test_must_have_missing_lowers_score(embedder, skills):
    jd = "Requirements\n- Rust and Kafka in production\n- Terraform on AWS\n"
    weak = match(RESUME, jd, embedder, skills)
    strong = match(RESUME, "Requirements\n- Python and FastAPI\n- PostgreSQL\n", embedder, skills)
    assert weak.score < 30 < strong.score
    assert "Missing must-have skills" in " ".join(weak.summary)


def test_better_resume_ranks_higher(embedder, skills):
    other = "PROJECTS\n- Made posters in Canva for the college fest\n- Edited videos\n"
    m = JobMatcher(JD, embedder, skills)
    assert m.score_text(RESUME).score > m.score_text(other).score


def test_empty_jd_raises(embedder, skills):
    with pytest.raises(NoRequirements):
        JobMatcher("About us\nWe are a great team.\n", embedder, skills)


def test_implied_by_used_skill_beats_listed(embedder, skills):
    resume = "EXPERIENCE\n- Fine-tuned a BERT model in PyTorch for ticket routing\n\nSKILLS\nPython, PyTorch\n"
    r = match(resume, "Requirements\n- Strong Python\n", embedder, skills)
    assert skill(r, "Python").status == "implied"


def test_requirement_with_found_skill_is_never_missing(embedder, skills):
    resume = "PROJECTS\n- Made posters for the college fest\n\nSKILLS\nDocker\n"
    r = match(resume, "Nice to have\n- Docker\n", embedder, skills)
    assert r.requirements[0].status != "missing"


def test_skill_reported_once_in_summary(embedder, skills):
    jd = "What you'll do\n- Build LLM features\n\nRequirements\n- Prompt engineering and LLM output\n"
    r = match("PROJECTS\n- Made posters for the college fest\n", jd, embedder, skills)
    text = " ".join(r.summary)
    assert text.count("LLMs") == 1
    assert "Missing must-have skills" in text and "Also not found" not in text


def test_listed_alternative_hidden_when_other_option_is_shown(embedder, skills):
    resume = "PROJECTS\n- Built a ledger API with FastAPI\n\nSKILLS\nFastAPI, Django\n"
    r = match(resume, "Requirements\n- FastAPI or Django\n", embedder, skills)
    assert [s.name for s in r.skills] == ["FastAPI"]
    assert not any("Django" in line for line in r.summary)


def test_missing_must_keeps_alternatives_together(embedder, skills):
    r = match(
        "PROJECTS\n- Made posters for the college fest\n", "Requirements\n- FastAPI or Django\n", embedder, skills
    )
    assert r.missing_must == ["Django or FastAPI"]
