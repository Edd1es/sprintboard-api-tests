"""API test suite for SprintBoard: functional, negative, contract and business-rule tests."""
import time
import pytest, requests
from jsonschema import validate
from conftest import BASE_URL

TASK_SCHEMA = {
    "type": "object",
    "required": ["id", "title", "priority", "assignee", "status", "created_at"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "title": {"type": "string", "minLength": 3, "maxLength": 80},
        "priority": {"type": "integer", "minimum": 1, "maximum": 5},
        "assignee": {"type": ["string", "null"]},
        "status": {"enum": ["todo", "in_progress", "done"]},
        "created_at": {"type": "string"},
    },
    "additionalProperties": False,
}

# ---------- Positive / CRUD ----------
def test_create_task_returns_201_and_body(api):
    r = api.post(f"{BASE_URL}/tasks", json={"title": "Set up CI", "priority": 1, "assignee": "Eddie"})
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Set up CI" and body["status"] == "todo"
    assert r.headers["content-type"].startswith("application/json")


def test_get_task_by_id(api, make_task):
    t = make_task()
    r = api.get(f"{BASE_URL}/tasks/{t['id']}")
    assert r.status_code == 200 and r.json() == t


def test_list_sorted_by_priority(api, make_task):
    make_task("Low task", 5); make_task("High task", 1); make_task("Mid task", 3)
    titles = [t["title"] for t in api.get(f"{BASE_URL}/tasks").json()]
    assert titles == ["High task", "Mid task", "Low task"]


def test_filter_by_query_params(api, make_task):
    a = make_task("Urgent bug", 1); make_task("Nice-to-have", 4)
    api.patch(f"{BASE_URL}/tasks/{a['id']}/status", json={"status": "in_progress"})
    r = api.get(f"{BASE_URL}/tasks", params={"status_filter": "in_progress", "max_priority": 2})
    assert [t["id"] for t in r.json()] == [a["id"]]


def test_delete_task_then_404(api, make_task):
    t = make_task()
    assert api.delete(f"{BASE_URL}/tasks/{t['id']}").status_code == 204
    assert api.get(f"{BASE_URL}/tasks/{t['id']}").status_code == 404

# ---------- Contract (schema) ----------
def test_response_matches_schema(api, make_task):
    validate(instance=make_task(assignee=None), schema=TASK_SCHEMA)
    for task in api.get(f"{BASE_URL}/tasks").json():
        validate(instance=task, schema=TASK_SCHEMA)

# ---------- Negative / validation (data-driven) ----------
@pytest.mark.parametrize("payload, reason", [
    ({"title": "ab", "priority": 2}, "title too short"),
    ({"title": "x" * 81, "priority": 2}, "title too long"),
    ({"title": "Valid", "priority": 0}, "priority below range"),
    ({"title": "Valid", "priority": 6}, "priority above range"),
    ({"title": "Valid", "priority": "high"}, "priority wrong type"),
    ({"priority": 2}, "missing title"),
    ({"title": "   ", "priority": 2}, "whitespace-only title"),
])
def test_invalid_payloads_return_422(api, payload, reason):
    r = api.post(f"{BASE_URL}/tasks", json=payload)
    assert r.status_code == 422, f"{reason}: expected 422, got {r.status_code}"


def test_unknown_task_returns_404(api):
    r = api.get(f"{BASE_URL}/tasks/9999")
    assert r.status_code == 404 and r.json()["detail"] == "Task not found"

# ---------- Security ----------
@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "wrong-key"}])
def test_requests_without_valid_key_are_rejected(headers):
    r = requests.get(f"{BASE_URL}/tasks", headers=headers)
    assert r.status_code == 401

# ---------- Business rules ----------
def test_status_moves_forward(api, make_task):
    t = make_task()
    for s in ["in_progress", "done"]:
        r = api.patch(f"{BASE_URL}/tasks/{t['id']}/status", json={"status": s})
        assert r.status_code == 200 and r.json()["status"] == s


def test_status_cannot_move_backward(api, make_task):
    t = make_task()
    api.patch(f"{BASE_URL}/tasks/{t['id']}/status", json={"status": "done"})
    r = api.patch(f"{BASE_URL}/tasks/{t['id']}/status", json={"status": "todo"})
    assert r.status_code == 409 and "back to todo" in r.json()["detail"]


def test_done_task_cannot_be_deleted(api, make_task):
    t = make_task()
    api.patch(f"{BASE_URL}/tasks/{t['id']}/status", json={"status": "done"})
    assert api.delete(f"{BASE_URL}/tasks/{t['id']}").status_code == 409
    assert api.get(f"{BASE_URL}/tasks/{t['id']}").status_code == 200

# ---------- Performance smoke ----------
def test_list_responds_under_200ms_with_100_tasks(api, make_task):
    for i in range(100):
        make_task(f"Bulk task {i}", (i % 5) + 1)
    start = time.perf_counter()
    r = api.get(f"{BASE_URL}/tasks")
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert r.status_code == 200 and len(r.json()) == 100
    assert elapsed_ms < 200, f"took {elapsed_ms:.0f} ms"
