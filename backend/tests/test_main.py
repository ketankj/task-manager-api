from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _register_and_login(username="alice", password="supersecret123"):
    client.post("/auth/register", json={"username": username, "password": password})
    resp = client.post("/auth/login", data={"username": username, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_register_and_login():
    token = _register_and_login("bob", "hunter2pass")
    assert token


def test_login_wrong_password():
    client.post("/auth/register", json={"username": "carol", "password": "correctpass1"})
    resp = client.post("/auth/login", data={"username": "carol", "password": "wrongpass1"})
    assert resp.status_code == 401


def test_tasks_require_auth():
    resp = client.get("/api/tasks")
    assert resp.status_code == 401


def test_create_and_list_task():
    token = _register_and_login("dave", "password1234")
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/tasks", json={"title": "Write CI pipeline"}, headers=headers)
    assert resp.status_code == 201
    task = resp.json()
    assert task["status"] == "open"

    resp = client.get("/api/tasks", headers=headers)
    assert resp.status_code == 200
    assert any(t["title"] == "Write CI pipeline" for t in resp.json())


def test_update_task_status():
    token = _register_and_login("erin", "password5678")
    headers = {"Authorization": f"Bearer {token}"}
    task = client.post("/api/tasks", json={"title": "Review PR"}, headers=headers).json()

    resp = client.patch(f"/api/tasks/{task['id']}", json={"status": "done"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"


def test_cannot_update_other_users_task():
    token_a = _register_and_login("frank", "passwordAAAA")
    token_b = _register_and_login("grace", "passwordBBBB")

    task = client.post(
        "/api/tasks", json={"title": "Frank's task"}, headers={"Authorization": f"Bearer {token_a}"}
    ).json()

    resp = client.patch(
        f"/api/tasks/{task['id']}",
        json={"status": "done"},
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 403
