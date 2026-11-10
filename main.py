# main.py
# FastAPI backend for a simple TODO application.
# Provides endpoints to create, read, update, and delete tasks.
# Author: Joseph Yep
# Date: 2025-05-27

from fastapi import FastAPI, HTTPException, status
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


# Initialize storage and FastAPI app
storage = TaskStorage()
app = FastAPI(title="Todo API", description="A simple Todo application API", version="1.0.0")

# Enable CORS for all origins (for frontend integration)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "*"],  # Add your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_model=dict)
def root():
    """Health check endpoint"""
    return {"message": "Todo API is running", "timestamp": datetime.now()}


@app.get("/tasks", response_model=List[Task])
def get_tasks():
    """Get all tasks"""
    tasks = storage.get_all()
    logger.info(f"Retrieved {len(tasks)} tasks")
    return tasks


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    """Create a new task"""
    if not task.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title cannot be empty")

    # Check for duplicate titles (optional business rule)
    existing_tasks = storage.get_all()
    if any(t.title.lower() == task.title.strip().lower() and not t.completed for t in existing_tasks):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A task with this title already exists")

    return storage.create(task)


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    """Get a specific task by ID"""
    task = storage.get_by_id(task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} not found")
    return task


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, updated: TaskUpdate):
    """Update an existing task by ID"""
    if not updated.title.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title cannot be empty")

    task = storage.update(task_id, updated)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} not found")
    return task


@app.delete("/tasks/{task_id}", response_model=dict, status_code=status.HTTP_200_OK)
def delete_task(task_id: int):
    """Delete a task by ID"""
    success = storage.delete(task_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task with id {task_id} not found")
    return {"detail": "Task deleted"}


@app.get("/tasks/stats", response_model=dict)
def get_task_stats():
    """Get task statistics"""
    tasks = storage.get_all()
    total = len(tasks)
    completed = sum(1 for t in tasks if t.completed)
    pending = total - completed

    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "completion_rate": round((completed / total * 100) if total > 0 else 0, 1),
    }
