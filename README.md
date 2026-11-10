# 🚀 FastAPI Backend

A robust REST API backend for the Task Master todo application built with FastAPI, featuring comprehensive task management, validation, and error handling.

## 📋 Features

- **Full CRUD Operations**: Create, read, update, and delete tasks
- **Data Validation**: Comprehensive input validation using Pydantic models
- **Error Handling**: Proper HTTP status codes and error messages
- **CORS Support**: Configured for frontend integration
- **Logging**: Structured logging for debugging and monitoring
- **Statistics Endpoint**: Task completion metrics and analytics
- **Duplicate Prevention**: Business logic to prevent duplicate task titles
- **Auto-documentation**: Interactive API docs with Swagger UI
- **Testing**: Comprehensive test suite with pytest

## 🛠️ Tech Stack

- **Framework**: FastAPI 0.104+
- **Python**: 3.8+
- **Validation**: Pydantic models
- **Testing**: pytest + TestClient
- **Server**: Uvicorn ASGI server
- **Deployment**: Render.com ready configuration

## 📦 Project Structure

``` sh
backend/
├── main.py              # Main application file
├── worker.py            # Cloudflare Workers entrypoint
├── wrangler.jsonc       # Workers and D1 configuration
├── pyproject.toml       # Python Workers dependencies
├── migrations/          # D1 schema migrations
├── requirements.txt     # Python dependencies
├── render.yaml         # Render.com deployment configuration
└── test/
    └── test_main.py    # Test suite
```

## ⚙️ Prerequisites

- **Python** >= 3.8
- **pip** (Python package installer)

## 🚀 Getting Started

### 1. Installation

```bash
# Clone the repository (if not already done)
git clone <your-repo-url>
cd todo_app/backend

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Running the Development Server

```bash
# Start the server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# The API will be available at:
# - API: http://localhost:8000
# - Interactive docs: http://localhost:8000/docs
# - Alternative docs: http://localhost:8000/redoc
```

### 3. Testing

```bash
# Run all tests
pytest

# Run tests with verbose output
pytest -v

# Run tests with coverage
pytest --cov=main
```

## 📚 API Documentation

### Base URL

``` http
http://localhost:8000
```

### Endpoints

#### Health Check

```http
GET /
```

Returns API status and timestamp.

**Response:**

```json
{
  "message": "Todo API is running",
  "timestamp": "2025-06-06T10:30:00.000Z"
}
```

#### Get All Tasks

```http
GET /tasks
```

Retrieve all tasks.

**Response:**

```json
[
  {
    "id": 1,
    "title": "Complete project",
    "completed": false,
    "created_at": "2025-06-06T10:30:00.000Z",
    "updated_at": null
  }
]
```

#### Create Task

```http
POST /tasks
```

**Request Body:**

```json
{
  "title": "New task title",
  "completed": false
}
```

**Response:** `201 Created`

```json
{
  "id": 2,
  "title": "New task title",
  "completed": false,
  "created_at": "2025-06-06T10:30:00.000Z",
  "updated_at": null
}
```

#### Get Single Task

```http
GET /tasks/{task_id}
```

**Response:**

```json
{
  "id": 1,
  "title": "Complete project",
  "completed": false,
  "created_at": "2025-06-06T10:30:00.000Z",
  "updated_at": null
}
```

#### Update Task

```http
PUT /tasks/{task_id}
```

**Request Body:**

```json
{
  "title": "Updated task title",
  "completed": true
}
```

**Response:**

```json
{
  "id": 1,
  "title": "Updated task title",
  "completed": true,
  "created_at": "2025-06-06T10:30:00.000Z",
  "updated_at": "2025-06-06T11:00:00.000Z"
}
```

#### Delete Task

```http
DELETE /tasks/{task_id}
```

**Response:**

```json
{
  "detail": "Task deleted"
}
```

#### Get Task Statistics

```http
GET /tasks/stats
```

**Response:**

```json
{
  "total": 10,
  "completed": 6,
  "pending": 4,
  "completion_rate": 60.0
}
```

## 🏗️ Architecture

### Data Models

#### Task Model

```python
class Task(BaseModel):
    id: int
    title: str
    completed: bool = False
    created_at: datetime
    updated_at: Optional[datetime] = None
```

#### Input Models

- **TaskCreate**: For creating new tasks
- **TaskUpdate**: For updating existing tasks

### Storage Layer

Cloudflare Workers requests use the bound D1 database for persistent task storage. Running the FastAPI app directly with Uvicorn (without a Workers environment) uses in-memory storage for local development; that data is not persistent.

### Business Logic

- **Duplicate Prevention**: Prevents duplicate task titles for incomplete tasks
- **Input Validation**: Automatic validation via Pydantic models
- **Error Handling**: Comprehensive HTTP error responses
- **Logging**: Structured logging for all operations

## 🔒 Error Handling

The API returns appropriate HTTP status codes:

- `200 OK`: Successful operations
- `201 Created`: Successful task creation
- `400 Bad Request`: Invalid input data
- `404 Not Found`: Task not found
- `409 Conflict`: Duplicate task title

Example error response:

```json
{
  "detail": "Task with id 999 not found"
}
```

## 🚀 Deployment

### Render.com (Configured)

The project includes `render.yaml` for easy deployment:

```yaml
services:
  - type: web
    name: todo-backend
    env: python
    buildCommand: "pip install -r requirements.txt"
    startCommand: "uvicorn main:app --host 0.0.0.0 --port 8000"
```

### Cloudflare Workers and D1

The Worker uses the existing FastAPI application and the D1 binding configured in `wrangler.jsonc`. The Python Workers runtime requires Python 3.13+, Node.js, and `uv`.

1. From `backend/`, create a D1 database and copy its ID into `wrangler.jsonc` in place of `REPLACE_WITH_D1_DATABASE_ID`:

  ```bash
  uv run pywrangler d1 create todo-db
  ```

2. Apply the schema locally, then start the Worker:

  ```bash
  uv run pywrangler d1 migrations apply todo-db --local
  uv run pywrangler dev
  ```

3. Apply the schema to the remote database and deploy:

  ```bash
  uv run pywrangler d1 migrations apply todo-db --remote
  uv run pywrangler deploy
  ```

The Worker exposes the API and FastAPI docs at its assigned `workers.dev` URL. For Cloudflare Pages, set the frontend project root to `frontend`, build with `npm run build`, and use `dist` as the output directory. Set the Pages environment variable `VITE_API_URL` to the deployed Worker URL (without a trailing slash), then redeploy the frontend.

The production CORS allowlist includes `https://todo-app.pages.dev`; update it in `main.py` if the Pages project uses another hostname. Keep `frontend/.env` local and use `.env.example` as the non-secret template.

### Manual Deployment

```bash
# Install dependencies
pip install -r requirements.txt

# Start production server
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Docker (Optional)

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🧪 Testing

The test suite covers:

- Task creation and retrieval
- Task updates and completion
- Task deletion
- Error scenarios
- API response validation

Run specific tests:

```bash
# Test task operations
pytest test/test_main.py::test_create_and_get_tasks -v

# Test update and delete
pytest test/test_main.py::test_update_and_delete_task -v
```

## 🔧 Configuration

### CORS Settings

The API is configured to accept requests from:

- `http://localhost:5173` (Vite dev server)
- `http://127.0.0.1:5173`
- `https://todo-app.pages.dev` (Cloudflare Pages)

### Logging

Configured at INFO level. Logs include:

- Task creation events
- Task updates
- Task deletions
- Request information

## 📈 Performance

- **D1 Storage on Workers**: Persistent SQLite-compatible storage
- **Async Framework**: FastAPI's async capabilities
- **Auto-generated Docs**: Swagger UI for easy API exploration
- **Input Validation**: Automatic request/response validation

## 🤝 Contributing

1. Follow PEP 8 style guidelines
2. Add tests for new features
3. Update documentation as needed
4. Ensure all tests pass: `pytest -v`

## 📝 Requirements

See [`requirements.txt`](requirements.txt) for the complete list of dependencies:

```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
pytest>=7.0.0
httpx>=0.25.0
```

## 📄 API Schema

The API automatically generates OpenAPI schema available at:

- **Swagger UI**: `/docs`
- **ReDoc**: `/redoc`
- **OpenAPI JSON**: `/openapi.json`
