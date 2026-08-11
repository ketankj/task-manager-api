# Task Manager API

A REST + WebSocket task management service built with **FastAPI**, featuring
JWT-based authentication implemented from Python's standard library
(no auth framework dependency), per-user task ownership, and real-time task
updates pushed over WebSockets.

## Stack

- **Backend:** Python, FastAPI, SQLite, WebSockets, pytest
- **Auth:** Hand-rolled JWT (HS256) + PBKDF2 password hashing, both stdlib-only
- **Ops:** Docker, GitHub Actions CI

## Run locally

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Run tests

```bash
cd backend
pytest -v
```

## Endpoints

| Method | Path              | Auth | Description                          |
|--------|-------------------|------|---------------------------------------|
| POST   | /auth/register    | No   | Create a user                        |
| POST   | /auth/login        | No   | Get a JWT access token               |
| GET    | /api/tasks         | Yes  | List the current user's tasks        |
| POST   | /api/tasks         | Yes  | Create a task                        |
| PATCH  | /api/tasks/{id}    | Yes  | Update task status                   |
| DELETE | /api/tasks/{id}    | Yes  | Delete a task                        |
| WS     | /ws/tasks?token=…  | Yes  | Real-time task create/update events  |
| GET    | /health            | No   | Health check                         |

## Example flow

```bash
curl -X POST localhost:8000/auth/register -H "Content-Type: application/json" \
  -d '{"username":"ketan","password":"strongpassword1"}'

curl -X POST localhost:8000/auth/login \
  -d "username=ketan&password=strongpassword1"
# -> {"access_token": "...", "token_type": "bearer"}

curl -X POST localhost:8000/api/tasks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Ship the CI pipeline"}'
```

## Next steps / ideas to extend

- Add refresh tokens and token revocation
- Move from SQLite to Postgres with SQLAlchemy models
- Add role-based access control (admin vs. user)
- Build a small React frontend that opens the WebSocket and live-updates a task board

## License

MIT — see [LICENSE](LICENSE).
