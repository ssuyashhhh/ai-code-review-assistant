# 🤖 AI Code Review Assistant — Backend

A **FastAPI** backend that sends source code to **OpenAI GPT** and returns a fully structured code review.

---

## 📁 Project Structure

```
code review/
├── main.py            # FastAPI app — OpenAI integration + structured review
├── requirements.txt   # Python dependencies
├── .env               # Secret env vars (OPENAI_API_KEY) — never commit
├── .env.example       # Safe template to commit
└── .gitignore         # Excludes .env and cache
```

---

## ⚙️ Setup & Installation

### 1. Create and activate a virtual environment

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your OpenAI API key

```bash
copy .env.example .env    # Windows
cp .env.example .env      # macOS / Linux
```

Open `.env` and replace the placeholder:

```
OPENAI_API_KEY=sk-...your-real-key-here...
OPENAI_MODEL=gpt-4o          # optional — defaults to gpt-4o
```

---

## ▶️ Running the Server

```bash
python -m uvicorn main:app --reload
```

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:8000/` | Health check |
| `http://127.0.0.1:8000/docs` | Interactive Swagger UI |
| `http://127.0.0.1:8000/redoc` | ReDoc documentation |

---

## 🧪 Testing the Endpoint

### Option A — Swagger UI (easiest)

1. Navigate to `http://127.0.0.1:8000/docs`
2. Click `POST /review` → **Try it out**
3. Paste the request body below and click **Execute**

### Option B — PowerShell

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/review" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{
    "code": "def find_max(lst):\n    max_val = 0\n    for i in range(len(lst)):\n        for j in range(len(lst)):\n            if lst[i] > max_val:\n                max_val = lst[i]\n    return max_val",
    "language": "python"
  }'
```

### Option C — curl

```bash
curl -X POST http://127.0.0.1:8000/review \
  -H "Content-Type: application/json" \
  -d '{
    "code": "def find_max(lst):\n    max_val = 0\n    for i in range(len(lst)):\n        for j in range(len(lst)):\n            if lst[i] > max_val:\n                max_val = lst[i]\n    return max_val",
    "language": "python"
  }'
```

---

## 📦 Request & Response Format

### Request Body

```json
{
  "code": "def find_max(lst): ...",
  "language": "python"
}
```

### ✅ Success Response `200 OK`

```json
{
  "status": "success",
  "language": "python",
  "model_used": "gpt-4o",
  "bugs": [
    {
      "line": "2",
      "description": "Initialising max_val to 0 causes incorrect results for all-negative lists.",
      "severity": "high",
      "suggestion": "Use float('-inf') or lst[0] as the initial value."
    }
  ],
  "time_complexity": "O(n²) — the nested loop iterates over the entire list twice, but the inner loop does no useful work. Can be reduced to O(n).",
  "optimizations": [
    "Eliminate the inner loop entirely — only one pass is needed.",
    "Use Python's built-in max() for an idiomatic O(n) solution."
  ],
  "clean_code": [
    "Rename lst to numbers or values for clarity.",
    "Add a guard for empty input and raise ValueError with a descriptive message."
  ],
  "overall_summary": "The function has a critical bug with negative numbers and an unnecessary nested loop making it O(n²). Replacing the double-loop with a single pass and fixing the initialisation are the top priorities."
}
```

### ❌ Error Responses

| Status | Cause |
|--------|-------|
| `422` | Missing or invalid `code` / `language` field (Pydantic) |
| `503` | `OPENAI_API_KEY` not set in `.env` |
| `502` | OpenAI API returned an error |
| `500` | Model returned malformed JSON |

---

## 🔌 Available Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Health check + readiness flag |
| POST | `/review` | AI-powered structured code review |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc UI |

---

## 🔒 Security Notes

- **Never** commit `.env` — it's in `.gitignore`.
- In production, replace `allow_origins=["*"]` with your frontend domain.
- Use environment-specific `.env` files (`.env.production`, etc.) or a secrets manager.
