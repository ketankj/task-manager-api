from pydantic import BaseModel, Field
from typing import Literal

TaskStatus = Literal["open", "in_progress", "done"]


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""


class TaskUpdate(BaseModel):
    status: TaskStatus


class TaskOut(BaseModel):
    id: int
    owner_id: int
    title: str
    description: str
    status: TaskStatus
    created_at: str
