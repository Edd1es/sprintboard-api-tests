"""SprintBoard API - a small task-tracking REST API used as the system under test.

Rules enforced by the API (and verified by the test suite):
  * Every request needs header  X-API-Key: capstone-key
  * Task titles are 3-80 characters; priority is 1 (high) to 5 (low)
  * Status may only move forward: todo -> in_progress -> done
  * A task that is 'done' cannot be deleted (it is kept for sprint history)
"""
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import BaseModel, Field

API_KEY = "capstone-key"
ORDER = ["todo", "in_progress", "done"]

app = FastAPI(title="SprintBoard API", version="1.0")
_tasks: dict[int, dict] = {}
_next_id = 1


def require_key(x_api_key: Optional[str] = Header(default=None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


class TaskIn(BaseModel):
    title: str = Field(min_length=3, max_length=80)
    priority: int = Field(ge=1, le=5)
    assignee: Optional[str] = None


class StatusIn(BaseModel):
    status: Literal["todo", "in_progress", "done"]


@app.post("/reset", status_code=204, dependencies=[Depends(require_key)])
def reset():
    global _next_id
    _tasks.clear()
    _next_id = 1
    return Response(status_code=204)


@app.post("/tasks", status_code=201, dependencies=[Depends(require_key)])
def create_task(body: TaskIn):
    global _next_id
    title = body.title.strip()
    if len(title) < 3:  # fix for bug caught by the "whitespace-only title" test case
        raise HTTPException(status_code=422, detail="Title cannot be blank")
    task = {"id": _next_id, "title": title, "priority": body.priority,
            "assignee": body.assignee, "status": "todo",
            "created_at": datetime.now(timezone.utc).isoformat()}
    _tasks[_next_id] = task
    _next_id += 1
    return task


@app.get("/tasks", dependencies=[Depends(require_key)])
def list_tasks(status_filter: Optional[str] = None, max_priority: Optional[int] = None):
    items = list(_tasks.values())
    if status_filter:
        items = [t for t in items if t["status"] == status_filter]
    if max_priority:
        items = [t for t in items if t["priority"] <= max_priority]
    return sorted(items, key=lambda t: (t["priority"], t["id"]))


@app.get("/tasks/{task_id}", dependencies=[Depends(require_key)])
def get_task(task_id: int):
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return _tasks[task_id]


@app.patch("/tasks/{task_id}/status", dependencies=[Depends(require_key)])
def move_task(task_id: int, body: StatusIn):
    task = get_task(task_id)
    if ORDER.index(body.status) < ORDER.index(task["status"]):
        raise HTTPException(status_code=409,
                            detail=f"Cannot move task from {task['status']} back to {body.status}")
    task["status"] = body.status
    return task


@app.delete("/tasks/{task_id}", status_code=204, dependencies=[Depends(require_key)])
def delete_task(task_id: int):
    task = get_task(task_id)
    if task["status"] == "done":
        raise HTTPException(status_code=409, detail="Completed tasks are kept for sprint history")
    del _tasks[task_id]
    return Response(status_code=204)
