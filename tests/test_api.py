"""API tests. Run with: uv run --with pytest --with httpx python -m pytest -v

Outside Workers there is no D1 binding, so the app falls back to in-memory storage.
"""

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def setup_function():
    main.storage = main.TaskStorage()


def test_health():
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["message"] == "Todo API is running"


def test_create_and_list():
    r = client.post("/tasks", json={"title": "Buy milk"})
    assert r.status_code == 201
    task = r.json()
    assert task["title"] == "Buy milk"
    assert task["completed"] is False

    r = client.get("/tasks")
    assert r.status_code == 200
    assert [t["title"] for t in r.json()] == ["Buy milk"]


def test_update_and_delete():
    task_id = client.post("/tasks", json={"title": "Write tests"}).json()["id"]

    r = client.put(f"/tasks/{task_id}", json={"title": "Write tests", "completed": True})
    assert r.status_code == 200
    assert r.json()["completed"] is True

    assert client.delete(f"/tasks/{task_id}").status_code in (200, 204)
    assert client.get("/tasks").json() == []


def test_empty_title_rejected():
    assert client.post("/tasks", json={"title": ""}).status_code == 422


def test_cors_allows_frontend():
    origin = "https://cloudflare-test-frontend.blackjackwarriors.workers.dev"
    r = client.options(
        "/tasks",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") == origin
