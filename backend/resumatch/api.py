from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from .embedding import get_embedder
from .matcher import JobMatcher, NoRequirements
from .pdf import PDFError, extract_text
from .schemas import MatchResult, RankedResume, RankResult
from .skills import default_index

MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_RANK_FILES = 25
MAX_JD_CHARS = 20_000


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Loading MiniLM takes a few seconds; do it before the first request does.
    get_embedder()
    default_index()
    yield


app = FastAPI(title="ResuMatch", version="0.1.0", lifespan=lifespan)

origins = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


def _matcher(jd_text: str) -> JobMatcher:
    jd_text = jd_text.strip()
    if not jd_text:
        raise HTTPException(422, "Paste a job description.")
    if len(jd_text) > MAX_JD_CHARS:
        raise HTTPException(422, "That job description is unusually long. Trim it to the role itself.")
    try:
        return JobMatcher(jd_text, get_embedder(), default_index())
    except NoRequirements as e:
        raise HTTPException(422, str(e)) from None


async def _read_pdf(upload: UploadFile) -> str:
    data = await upload.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise PDFError("File is larger than 5 MB.")
    return await run_in_threadpool(extract_text, data)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "embedder": get_embedder().name}


@app.post("/api/match", response_model=MatchResult)
async def match_one(
    jd_text: str = Form(...),
    resume: UploadFile | None = File(None),
    resume_text: str | None = Form(None),
) -> MatchResult:
    if resume is not None:
        try:
            text = await _read_pdf(resume)
        except PDFError as e:
            raise HTTPException(422, str(e)) from None
    elif resume_text and resume_text.strip():
        text = resume_text
    else:
        raise HTTPException(422, "Upload a resume PDF or paste its text.")

    matcher = _matcher(jd_text)
    return await run_in_threadpool(matcher.score_text, text)


@app.post("/api/rank", response_model=RankResult)
async def rank(jd_text: str = Form(...), resumes: list[UploadFile] = File(...)) -> RankResult:
    if len(resumes) > MAX_RANK_FILES:
        raise HTTPException(422, f"Up to {MAX_RANK_FILES} resumes at a time.")
    matcher = _matcher(jd_text)

    out: list[RankedResume] = []
    for f in resumes:
        name = f.filename or "resume.pdf"
        try:
            text = await _read_pdf(f)
        except PDFError as e:
            out.append(RankedResume(filename=name, score=None, error=str(e)))
            continue
        res = await run_in_threadpool(matcher.score_text, text)
        out.append(
            RankedResume(
                filename=name,
                score=res.score,
                must_coverage=res.must_coverage,
                missing_must=res.missing_must,
                result=res,
            )
        )

    # failed files go last; ties broken by must-have coverage
    out.sort(key=lambda r: (r.score is None, -(r.score or 0), -(r.must_coverage or 0)))
    return RankResult(candidates=out, requirement_count=len(matcher.jd.requirements))


# In the Docker image the built frontend is copied next to the backend and
# served from here, so the whole thing runs as one container.
STATIC_DIR = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist")).resolve()
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        target = STATIC_DIR / path
        if path and target.is_file() and STATIC_DIR in target.resolve().parents:
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
