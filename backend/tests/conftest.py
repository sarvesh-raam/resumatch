import os

# Tests never download a model. The hashing embedder is deterministic and
# good enough to check plumbing; MiniLM quality is what eval/ is for.
os.environ.setdefault("RESUMATCH_EMBEDDER", "hashing")

import fitz
import pytest

from resumatch.embedding import get_embedder
from resumatch.skills import default_index

RESUME = """\
Priya Nair
priya@example.com | github.com/priya

EXPERIENCE
Backend Intern | Acme Payments | Jun 2025 – Dec 2025
• Built REST APIs in FastAPI for the refunds service, backed by
PostgreSQL and deployed with Docker.
• Wrote pytest suites covering the settlement batch job.

PROJECTS
Chat app
• Real-time chat over WebSockets with a React frontend.

SKILLS
Python, SQL, Docker, Kubernetes, Git
"""

JD = """\
About us
We build payments software.

Requirements
- Strong Python and FastAPI or Django experience
- Experience with PostgreSQL
- Kubernetes in production
- 3+ years of professional experience

Nice to have
- Kafka experience
- Go is a plus

Benefits
- Free lunch
"""


@pytest.fixture(scope="session")
def skills():
    return default_index()


@pytest.fixture(scope="session")
def embedder():
    return get_embedder("hashing")


def make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    y = 50
    for line in text.splitlines():
        page.insert_text((50, y), line, fontsize=10)
        y += 14
    data = doc.tobytes()
    doc.close()
    return data
