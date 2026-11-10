# main.py
# FastAPI backend for a simple TODO application.
# Provides endpoints to create, read, update, and delete tasks.
# Author: Joseph Yep
# Date: 2025-05-27

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Task model for API responses
class Task(BaseModel):
    id: int
    title: str
    completed: bool = False
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


# Input model for creating tasks
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    completed: bool = False


# Input model for updating tasks
class TaskUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Task title")
    completed: bool = False


# Task storage class to manage state
class TaskStorage:
    def __init__(self):
        self._tasks: List[Task] = []
        self._counter = 1

    def get_all(self) -> List[Task]:
        return self._tasks.copy()

    def get_by_id(self, task_id: int) -> Optional[Task]:
        return next((task for task in self._tasks if task.id == task_id), None)

    def create(self, task_data: TaskCreate) -> Task:
        task = Task(id=self._counter, title=task_data.title.strip(), completed=task_data.completed)
        self._counter += 1
        self._tasks.append(task)
        logger.info(f"Created task {task.id}: {task.title}")
        return task

    def update(self, task_id: int, task_data: TaskUpdate) -> Optional[Task]:
        task = self.get_by_id(task_id)
        if task:
            task.title = task_data.title.strip()
            task.completed = task_data.completed
            task.updated_at = datetime.now()
            logger.info(f"Updated task {task_id}")
            return task
        return None

    def delete(self, task_id: int) -> bool:
        initial_count = len(self._tasks)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        success = len(self._tasks) < initial_count
        if success:
            logger.info(f"Deleted task {task_id}")
        return success


def _d1_database(request: Request):
    env = request.scope.get("env")
    if env is None:
        return None

    database = getattr(env, "DB", None)
    if database is None:
        raise HTTPException(status_code=503, detail="D1 database binding is unavailable")
    return database


def _to_python(value):
    converter = getattr(value, "to_py", None)
    return converter() if callable(converter) else value


def _result_property(result, name):
    result = _to_python(result)
    if isinstance(result, dict):
        return result.get(name)
    return getattr(result, name)


def _task_from_row(row) -> Task:
    return Task.parse_obj(_to_python(row))


async def _d1_tasks(database) -> List[Task]:
    result = await database.prepare(
        "SELECT id, title, completed, created_at, updated_at FROM tasks ORDER BY id"
    ).all()
    rows = _result_property(result, "results") or []
    return [_task_from_row(row) for row in _to_python(rows)]


async def _d1_task_by_id(database, task_id: int) -> Optional[Task]:
    row = await database.prepare(
        "SELECT id, title, completed, created_at, updated_at FROM tasks WHERE id = ?"
    ).bind(task_id).first()
    return _task_from_row(row) if row is not None else None


# Initialize storage and FastAPI app
storage = TaskStorage()
app = FastAPI(title="Todo API", description="A simple Todo application API", version="1.0.0")

# Allow the local Vite app and the production Cloudflare Pages app.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://todo-app.pages.dev",
        "https://cloudflare-test-frontend.blackjackwarriors.workers.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=dict)
def root():
    """Health check endpoint"""
    return {"message": "Todo API is running", "timestamp": datetime.now()}


@app.get("/tasks", response_model=List[Task])
async def get_tasks(request: Request):
    """Get all tasks"""
    database = _d1_database(request)
    tasks = await _d1_tasks(database) if database is not None else storage.get_all()
    logger.info(f"Retrieved {len(tasks)} tasks")
    return tasks


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
async def create_task(task: TaskCreate, request: Request):
    """Create a new task"""
    if not task.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title cannot be empty")

    # Check for duplicate titles (optional business rule)
    database = _d1_database(request)
    if database is None:
        duplicate_exists = any(
            t.title.lower() == task.title.strip().lower() and not t.completed
            for t in storage.get_all()
        )
    else:
        duplicate = await database.prepare(
            "SELECT id FROM tasks WHERE lower(title) = lower(?) AND completed = 0 LIMIT 1"
        ).bind(task.title.strip()).first()
        duplicate_exists = duplicate is not None
    if duplicate_exists:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A task with this title already exists")

    if database is None:
        return storage.create(task)

    row = await database.prepare(
        "INSERT INTO tasks (title, completed, created_at) VALUES (?, ?, ?) "
        "RETURNING id, title, completed, created_at, updated_at"
    ).bind(task.title.strip(), int(task.completed), datetime.now().isoformat()).first()
    return _task_from_row(row)


@app.get("/tasks/{task_id}", response_model=Task)
async def get_task(task_id: int, request: Request):
    """Get a specific task by ID"""
    database = _d1_database(request)
    task = await _d1_task_by_id(database, task_id) if database is not None else storage.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} not found")
    return task


@app.put("/tasks/{task_id}", response_model=Task)
async def update_task(task_id: int, updated: TaskUpdate, request: Request):
    """Update an existing task by ID"""
    if not updated.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title cannot be empty")

    database = _d1_database(request)
    if database is None:
        task = storage.update(task_id, updated)
    else:
        row = await database.prepare(
            "UPDATE tasks SET title = ?, completed = ?, updated_at = ? WHERE id = ? "
            "RETURNING id, title, completed, created_at, updated_at"
        ).bind(
            updated.title.strip(), int(updated.completed), datetime.now().isoformat(), task_id
        ).first()
        task = _task_from_row(row) if row is not None else None
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} not found")
    return task


@app.delete("/tasks/{task_id}", response_model=dict, status_code=status.HTTP_200_OK)
async def delete_task(task_id: int, request: Request):
    """Delete a task by ID"""
    database = _d1_database(request)
    if database is None:
        success = storage.delete(task_id)
    else:
        row = await database.prepare(
            "DELETE FROM tasks WHERE id = ? RETURNING id"
        ).bind(task_id).first()
        success = row is not None
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} not found")
    return {"detail": "Task deleted"}


@app.get("/tasks/stats", response_model=dict)
async def get_task_stats(request: Request):
    """Get task statistics"""
    database = _d1_database(request)
    if database is None:
        tasks = storage.get_all()
        total = len(tasks)
        completed = sum(1 for t in tasks if t.completed)
    else:
        result = await database.prepare(
            "SELECT COUNT(*) AS total, COALESCE(SUM(completed), 0) AS completed FROM tasks"
        ).first()
        result = _to_python(result)
        total = result["total"] if isinstance(result, dict) else result.total
        completed = result["completed"] if isinstance(result, dict) else result.completed
    pending = total - completed

    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "completion_rate": round((completed / total * 100) if total > 0 else 0, 1),
    }
