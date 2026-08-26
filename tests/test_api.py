"""HTTP contract tests for the dashboard's four endpoints.

These run against the real app with the mock LLM, so they exercise the whole
path — validation, routing, generation, dedup, serialisation — without a network
call or an API key.
"""

from __future__ import annotations

import pytest

from app.schemas.common import ContentType, Difficulty, Sport

CRICKET = Sport.CRICKET.value
MCQ = ContentType.MCQ.value
POLL = ContentType.POLL.value
TRUE_FALSE = ContentType.TRUE_FALSE.value


# --------------------------------------------------------------------- metadata


def test_root_points_at_the_docs(client):
    body = client.get("/").json()
    assert body["docs"] == "/docs"
    assert body["health"] == "/api/health"


def test_health_reports_every_dependency(client):
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["mock_mode"] is True  # tests never call the live API

    checks = body["checks"]
    assert checks["llm"]["mode"] == "mock"
    assert checks["llm"]["api_key_configured"] is False
    assert checks["web_search"]["enabled"] is False
    assert "knowledge_base" in checks
    assert "freshness" in checks


def test_health_tells_the_operator_how_to_seed_an_empty_knowledge_base(client):
    checks = client.get("/api/health").json()["checks"]["knowledge_base"]
    if checks["available"] and checks["documents"] == 0:
        assert "ingest_data.py" in checks["hint"]
        assert client.get("/api/health").json()["status"] == "degraded"


def test_meta_describes_all_five_formats(client):
    body = client.get("/api/meta").json()

    assert body["sports"] == [s.value for s in Sport]
    assert body["difficulties"] == [d.value for d in Difficulty]

    types = body["content_types"]
    assert {t["value"] for t in types} == {ct.value for ct in ContentType}
    for entry in types:
        assert entry["label"] and entry["contract"]
        assert entry["sticker"] and entry["surface"]

    poll = next(t for t in types if t["value"] == POLL)
    assert poll["fact_checked"] is False
    mcq = next(t for t in types if t["value"] == MCQ)
    assert mcq["fact_checked"] is True


# ------------------------------------------------------------------- generation


def test_generate_returns_a_mixed_batch_by_default(client):
    response = client.post(
        "/api/generate", json={"sport": CRICKET, "difficulty": "Medium", "count": 5}
    )
    assert response.status_code == 200

    body = response.json()
    assert body["batch_id"]
    assert len(body["items"]) == 5
    # An empty content_types means "mix all five", one of each at count=5.
    assert {i["content_type"] for i in body["items"]} == {ct.value for ct in ContentType}
    assert body["diagnostics"]["requested"] == 5
    assert body["diagnostics"]["returned"] == 5
    assert body["diagnostics"]["mock_mode"] is True


def test_generate_batch_carries_every_field_the_spec_asks_for(client):
    body = client.post(
        "/api/generate", json={"sport": CRICKET, "count": 5}
    ).json()

    by_type = {i["content_type"]: i for i in body["items"]}

    mcq = by_type[ContentType.MCQ.value]
    assert mcq["sport"] == CRICKET and mcq["difficulty"]
    assert mcq["question"] and len(mcq["options"]) == 4
    assert mcq["correct_answer"] in mcq["options"]
    assert mcq["explanation"]

    tf = by_type[ContentType.TRUE_FALSE.value]
    assert tf["statement"] and tf["answer"] in (True, False)
    assert tf["explanation"]

    poll = by_type[ContentType.POLL.value]
    assert poll["prompt"] and len(poll["options"]) == 2
    assert poll["correct_answer"] is None
    assert poll["opinion_based"] is True
    assert poll["grounding"]["fact_checked"] is False

    blank = by_type[ContentType.FILL_BLANK.value]
    assert "____" in blank["sentence"]
    assert len(blank["options"]) == 4 and blank["correct_answer"]

    number = by_type[ContentType.GUESS_NUMBER.value]
    assert isinstance(number["target"], (int, float))
    low, high = number["accepted_range"]
    assert low <= number["target"] <= high
    assert number["tolerance"] > 0


def test_generated_items_are_ready_to_paste_into_instagram(client):
    body = client.post("/api/generate", json={"sport": CRICKET, "count": 5}).json()
    for item in body["items"]:
        ig = item["instagram"]
        assert ig["prompt_text"] and ig["caption"]
        assert ig["sticker"] and ig["surface"]
        assert ig["hashtags"]
        assert 0 < item["engagement_score"] <= 100


def test_factual_items_cite_their_evidence_and_polls_do_not(client):
    body = client.post("/api/generate", json={"sport": CRICKET, "count": 5}).json()
    for item in body["items"]:
        grounding = item["grounding"]
        if item["content_type"] == ContentType.POLL.value:
            assert grounding["fact_checked"] is False
            assert grounding["resolved_sources"] == []
        else:
            assert grounding["fact_checked"] is True
            assert grounding["resolved_sources"], item["content_type"]
            kinds = {s["kind"] for s in grounding["resolved_sources"]}
            assert kinds  # each citation names the backend that supported it


def test_generate_reports_batch_insights(client):
    body = client.post("/api/generate", json={"sport": CRICKET, "count": 5}).json()

    insights = body["insights"]
    ids = {i["id"] for i in body["items"]}
    assert insights["count"] == len(body["items"])
    assert insights["best_item_id"] in ids
    assert 0 < insights["average_score"] <= 100
    assert sum(insights["type_mix"].values()) == len(body["items"])
    assert insights["opinion"] == 1  # exactly one poll in a five-type mix
    assert insights["grounded"] == 4


def test_generate_can_request_a_single_type(client):
    body = client.post(
        "/api/generate",
        json={"sport": Sport.FOOTBALL.value, "content_types": [POLL], "count": 3},
    ).json()

    assert len(body["items"]) == 3
    assert {i["content_type"] for i in body["items"]} == {POLL}
    # An opinion-only batch has nothing to fact-check, so web search is skipped.
    assert body["retrieval"]["web_search_used"] is False
    assert any("opinion-only" in m.lower() for m in body["retrieval"]["messages"])


def test_generate_reports_what_retrieval_contributed(client):
    body = client.post(
        "/api/generate",
        json={"sport": Sport.TENNIS.value, "difficulty": "Hard", "content_types": [MCQ]},
    ).json()

    retrieval = body["retrieval"]
    assert retrieval["notes"]
    assert retrieval["sources"]
    assert any("knowledge base sweep" in m for m in retrieval["messages"])
    assert set(retrieval).issuperset(
        {"web_search_used", "web_results", "vector_db_hits", "degraded"}
    )


def test_batch_items_are_unique_within_one_request(client):
    body = client.post(
        "/api/generate",
        json={"sport": Sport.BASKETBALL.value, "content_types": [MCQ], "count": 4},
    ).json()
    fingerprints = [i["fingerprint"] for i in body["items"]]
    assert len(set(fingerprints)) == len(fingerprints)


def test_repeated_requests_return_fresh_content(client):
    payload = {
        "sport": Sport.BADMINTON.value,
        "content_types": [TRUE_FALSE],
        "count": 3,
    }
    first = client.post("/api/generate", json=payload).json()
    second = client.post("/api/generate", json=payload).json()

    seen = {i["fingerprint"] for i in first["items"]}
    assert seen
    assert all(i["fingerprint"] not in seen for i in second["items"])


@pytest.mark.parametrize(
    "payload",
    [
        {"sport": "Quidditch"},
        {"sport": CRICKET, "count": 0},
        {"sport": CRICKET, "count": 99},
        {"sport": CRICKET, "difficulty": "Impossible"},
        {"sport": CRICKET, "content_types": ["Haiku"]},
        {"count": 3},  # sport is required
    ],
)
def test_generate_rejects_bad_requests(client, payload):
    assert client.post("/api/generate", json=payload).status_code == 422


def test_duplicate_content_types_are_collapsed(client):
    body = client.post(
        "/api/generate",
        json={"sport": CRICKET, "content_types": [MCQ, MCQ, POLL], "count": 4},
    ).json()
    assert {i["content_type"] for i in body["items"]} == {MCQ, POLL}
    assert len(body["items"]) == 4


# ----------------------------------------------------------------- regeneration


def test_regenerate_replaces_a_single_item(client):
    batch = client.post(
        "/api/generate",
        json={"sport": CRICKET, "content_types": [MCQ], "count": 2},
    ).json()
    original = batch["items"][0]

    response = client.post(
        "/api/regenerate",
        json={
            "sport": CRICKET,
            "content_type": MCQ,
            "avoid": [i["question"] for i in batch["items"]],
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["item"]["content_type"] == MCQ
    assert body["item"]["fingerprint"] != original["fingerprint"]
    assert body["diagnostics"]["requested"] == 1
    assert body["diagnostics"]["returned"] == 1


def test_regenerate_keeps_the_type_it_was_given(client):
    for content_type in ContentType:
        body = client.post(
            "/api/regenerate",
            json={"sport": Sport.FORMULA1.value, "content_type": content_type.value},
        ).json()
        assert body["item"]["content_type"] == content_type.value


def test_regenerate_explains_itself_when_nothing_valid_is_left(client):
    """Exhausting the pool must be a 422 with a reason, not an empty 200."""
    payload = {
        "sport": Sport.KABADDI.value,
        "content_type": ContentType.GUESS_NUMBER.value,
    }
    last = None
    for _ in range(12):
        last = client.post("/api/regenerate", json=payload)
        if last.status_code != 200:
            break

    if last.status_code == 200:
        pytest.skip("the kabaddi pool outlasted the attempt budget")

    assert last.status_code == 422
    assert last.json()["detail"]


def test_regenerate_rejects_a_missing_content_type(client):
    assert client.post("/api/regenerate", json={"sport": CRICKET}).status_code == 422


# ------------------------------------------------------------------- the schema


def test_openapi_documents_the_discriminated_item_union(client):
    schema = client.get("/openapi.json").json()
    assert "/api/generate" in schema["paths"]
    assert "/api/regenerate" in schema["paths"]

    names = set(schema["components"]["schemas"])
    for expected in ("MCQItem", "PollItem", "GuessNumberItem"):
        assert expected in names
