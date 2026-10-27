import pytest


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Python, SQL and Docker", {"Python", "SQL", "Docker"}),
        ("Wrote services in C++ and C#", {"C++", "C#"}),
        ("Used C for firmware", {"C"}),
        ("Built UIs in React and Next.js", {"React", "Next.js"}),
        ("deployed on k8s with helm", {"Kubernetes"}),
        ("postgres + redis", {"PostgreSQL", "Redis"}),
        ("JavaScript only", {"JavaScript"}),
    ],
)
def test_find(skills, text, expected):
    assert skills.find(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Able to react quickly to incidents",  # lowercase react is a verb
        "Worked in the R&D team",
        "Let's go over the design",
        "Rest of the team was remote",
        "excel at communication",
        "Built a Go-kart frame",
    ],
)
def test_no_false_positives(skills, text):
    assert skills.find(text) == set()


def test_java_not_inside_javascript(skills):
    assert "Java" not in skills.find("Strong JavaScript skills")


def test_implied_follows_chains(skills):
    implied = skills.implied_by({"Next.js"})
    assert implied["React"] == "Next.js"
    assert implied["JavaScript"] == "React"


def test_groups_split_and_or(skills):
    assert skills.groups("Python and FastAPI or Django") == [{"Python"}, {"FastAPI", "Django"}]
    assert skills.groups("Kafka, RabbitMQ, or Celery") == [{"Kafka", "RabbitMQ", "Celery"}]
    assert skills.groups("Python, SQL and Docker") == [{"Python"}, {"SQL"}, {"Docker"}]
    assert skills.groups("AWS/GCP") == [{"AWS", "GCP"}]


def test_spans_prefer_longest(skills):
    names = [name for _, _, name in skills.spans("spring boot and docker compose")]
    assert names == ["Spring Boot", "Docker"]
