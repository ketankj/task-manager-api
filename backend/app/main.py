from datetime import datetime, timezone

from fastapi import FastAPI, Depends, HTTPException, status, WebSocket, WebSocketDisconnect
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware

from .database import get_conn, init_db
from .auth import hash_password, verify_password, create_access_token, decode_access_token, TokenError
from .schemas import UserCreate, TokenResponse, TaskCreate, TaskUpdate, TaskOut

app = FastAPI(
    title="Task Manager API",
    description="A small REST + WebSocket service for managing tasks, with "
                 "JWT-based auth implemented from the standard library.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@app.on_event("startup")
def on_startup():
    init_db()


# ------------------------------------------------------------------- auth
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = decode_access_token(token)
    except TokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    with get_conn() as conn:
        row = conn.execute("SELECT id, username FROM users WHERE username = ?", (payload["sub"],)).fetchone()
    if row is None:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return {"id": row["id"], "username": row["username"]}


@app.post("/auth/register", status_code=201)
def register(user: UserCreate):
    with get_conn() as conn:
        existing = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (user.username, hash_password(user.password)),
        )
        conn.commit()
    return {"username": user.username}


@app.post("/auth/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends()):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (form.username,)).fetchone()

    if row is None or not verify_password(form.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")

    token = create_access_token(subject=row["username"])
    return TokenResponse(access_token=token)


# ------------------------------------------------------------------ tasks
@app.get("/api/tasks", response_model=list[TaskOut])
def list_tasks(current_user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE owner_id = ? ORDER BY created_at DESC", (current_user["id"],)
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/tasks", response_model=TaskOut, status_code=201)
async def create_task(task: TaskCreate, current_user: dict = Depends(get_current_user)):
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO tasks (owner_id, title, description, status, created_at) "
            "VALUES (?, ?, ?, 'open', ?)",
            (current_user["id"], task.title, task.description, created_at),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone()

    task_out = dict(row)
    await manager.broadcast(current_user["id"], {"event": "task_created", "task": task_out})
    return task_out


@app.patch("/api/tasks/{task_id}", response_model=TaskOut)
async def update_task_status(task_id: int, update: TaskUpdate, current_user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if row["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not your task")

        conn.execute("UPDATE tasks SET status = ? WHERE id = ?", (update.status, task_id))
        conn.commit()
        updated = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()

    task_out = dict(updated)
    await manager.broadcast(current_user["id"], {"event": "task_updated", "task": task_out})
    return task_out


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(task_id: int, current_user: dict = Depends(get_current_user)):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Task not found")
        if row["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not your task")
        conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        conn.commit()


# ------------------------------------------------------- websocket updates
class ConnectionManager:
    """Tracks active WebSocket connections per user and pushes task events
    to that user's connected clients in real time."""

    def __init__(self):
        self.active: dict[int, list[WebSocket]] = {}

    async def connect(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket):
        if user_id in self.active and websocket in self.active[user_id]:
            self.active[user_id].remove(websocket)

    async def broadcast(self, user_id: int, message: dict):
        for ws in self.active.get(user_id, []):
            await ws.send_json(message)


manager = ConnectionManager()


@app.websocket("/ws/tasks")
async def tasks_websocket(websocket: WebSocket, token: str):
    try:
        payload = decode_access_token(token)
    except TokenError:
        await websocket.close(code=4401)
        return

    with get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (payload["sub"],)).fetchone()
    if row is None:
        await websocket.close(code=4401)
        return

    user_id = row["id"]
    await manager.connect(user_id, websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive; client doesn't need to send data
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)


@app.get("/health")
def health():
    return {"status": "ok"}
