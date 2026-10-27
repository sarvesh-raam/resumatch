import pytest
from fastapi.testclient import TestClient

from resumatch.api import app

from .conftest import JD, RESUME, make_pdf

PDF = make_pdf(RESUME.replace("•", "-").replace("–", "-"))


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "embedder": "hashing"}


def test_match_pdf(client):
    r = client.post("/api/match", data={"jd_text": JD}, files={"resume": ("cv.pdf", PDF, "application/pdf")})
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["score"] <= 100
    assert body["requirements"]


def test_match_text(client):
    r = client.post("/api/match", data={"jd_text": JD, "resume_text": RESUME})
    assert r.status_code == 200


def test_match_needs_a_resume(client):
    r = client.post("/api/match", data={"jd_text": JD})
    assert r.status_code == 422
    assert "resume" in r.json()["detail"].lower()


def test_match_bad_file(client):
    r = client.post("/api/match", data={"jd_text": JD}, files={"resume": ("cv.pdf", b"not a pdf", "application/pdf")})
    assert r.status_code == 422
    assert "isn't a PDF" in r.json()["detail"]


def test_jd_without_requirements(client):
    r = client.post("/api/match", data={"jd_text": "We are hiring!", "resume_text": RESUME})
    assert r.status_code == 422


def test_rank_orders_and_keeps_failures(client):
    weak = make_pdf("PROJECTS\n- Designed posters for the college fest in Canva\n- Video editing for events\n")
    files = [
        ("resumes", ("weak.pdf", weak, "application/pdf")),
        ("resumes", ("broken.pdf", b"nope", "application/pdf")),
        ("resumes", ("strong.pdf", PDF, "application/pdf")),
    ]
    r = client.post("/api/rank", data={"jd_text": JD}, files=files)
    assert r.status_code == 200
    names = [c["filename"] for c in r.json()["candidates"]]
    assert names == ["strong.pdf", "weak.pdf", "broken.pdf"]
    assert r.json()["candidates"][-1]["error"]
