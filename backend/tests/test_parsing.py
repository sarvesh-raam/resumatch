import pytest

from resumatch.jd import MUST, NICE, parse_jd
from resumatch.pdf import PDFError, extract_text
from resumatch.resume import evidence_lines, parse_resume

from .conftest import JD, RESUME, make_pdf


def test_resume_sections():
    r = parse_resume(RESUME)
    assert r.sections == ["experience", "projects", "skills"]
    # contact line and name are dropped
    assert not any("@" in l.text for l in r.lines)


def test_wrapped_bullet_is_joined():
    r = parse_resume(RESUME)
    texts = [l.text for l in r.lines]
    assert any(t.startswith("Built REST APIs") and t.endswith("deployed with Docker.") for t in texts)


def test_bullet_glyph_on_its_own_line():
    r = parse_resume("PROJECTS\n•\nBuilt a thing with Flask and SQLite\n")
    assert [l.text for l in r.lines] == ["Built a thing with Flask and SQLite"]


def test_no_headings_falls_back_to_everything():
    r = parse_resume("Built dashboards in Tableau for the sales team\nWrote ETL jobs in Airflow\n")
    assert len(r.lines) == 2
    assert {l.section for l in r.lines} == {"other"}


def test_evidence_lines_skip_title_rows():
    lines = evidence_lines(parse_resume(RESUME))
    assert not any(l.text.startswith("Backend Intern") for l in lines)


def test_jd_kinds(skills):
    jd = parse_jd(JD, skills)
    by_text = {r.text: r for r in jd.requirements}
    assert by_text["Strong Python and FastAPI or Django experience"].kind == MUST
    assert by_text["Kafka experience"].kind == NICE
    assert by_text["Go is a plus"].kind == NICE
    # about-us and benefits blocks are ignored
    assert not any("lunch" in t or "payments software" in t for t in by_text)


def test_jd_years_reported_not_scored(skills):
    jd = parse_jd(JD, skills)
    assert jd.years == ["3+ years of professional experience"]
    assert not any("years" in r.text for r in jd.requirements)


def test_jd_short_skill_line_is_not_a_heading(skills):
    jd = parse_jd("Requirements\nStrong Python skills\nNice to have\nDocker\n", skills)
    assert [(r.text, r.kind) for r in jd.requirements] == [("Strong Python skills", MUST), ("Docker", NICE)]


def test_pdf_roundtrip():
    text = extract_text(make_pdf(RESUME.replace("•", "-").replace("–", "-")))
    assert "FastAPI" in text and "EXPERIENCE" in text


def test_pdf_rejects_non_pdf():
    with pytest.raises(PDFError, match="isn't a PDF"):
        extract_text(b"hello")


def test_pdf_rejects_empty():
    with pytest.raises(PDFError, match="almost no text"):
        extract_text(make_pdf(""))


def test_one_skill_per_line_is_kept():
    r = parse_resume("SKILLS\nDocker\nKubernetes\nPython\n")
    assert [l.text for l in r.lines] == ["Docker", "Kubernetes", "Python"]
