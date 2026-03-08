# 🤖 AI Code Review Assistant

A full-stack production-ready application that lets you paste code, send it to **DeepSeek AI** (via OpenRouter), and receive a detailed structured review — bugs, time/space complexity, optimizations, clean code suggestions, and AI-generated optimized code.

---

## ✨ Features

- 📝 **Monaco Editor** — VS Code-quality code editing
- 🔍 **Auto Language Detection** — automatically detects Python, C++, JavaScript, Java
- 📁 **File Upload** — upload `.py`, `.cpp`, `.js`, `.java` files directly
- 🐙 **GitHub File Review** — paste a GitHub blob URL to fetch and review any file
- 🔄 **PR Review Bot** — submit a GitHub Pull Request URL for AI-powered diff review
- 💡 **Optimized Code** — AI generates a complete rewritten version with all fixes applied
- 🛡️ **Rate Limiting** — 5 requests/minute per IP via SlowAPI
- 🔁 **Retry Logic** — auto-retries on 429 errors (3 retries, 20s delay)
- ✂️ **Input Truncation** — caps code at 3000 chars to stay within token limits

---

## 📁 Project Structure

```
ai-code-review-assistant/
├── backend/
│   ├── main.py            # FastAPI app + rate-limited endpoints
│   ├── llm_service.py     # OpenRouter/DeepSeek API client + retry logic
│   ├── github_service.py  # GitHub file fetch + PR diff extraction
│   ├── models.py          # Pydantic request/response schemas
│   ├── requirements.txt
│   ├── .env               # Your secrets (not committed)
│   └── .env.example
└── frontend/
    ├── components/
    │   ├── CodeEditor.jsx    # Monaco editor (VS Code)
    │   ├── ReviewPanel.jsx   # Structured review display
    │   ├── GitHubPanel.jsx   # GitHub file fetch UI
    │   └── PRPanel.jsx       # Pull request review UI
    ├── pages/
    │   ├── _app.js
    │   └── index.js          # Main split-pane layout
    ├── styles/
    │   └── globals.css
    ├── package.json
    ├── tailwind.config.js
    └── .env.local.example
```

---

## 🛠️ Tech Stack

| Layer     | Technology                          |
|-----------|-------------------------------------|
| Frontend  | Next.js, React, Tailwind CSS, Monaco Editor |
| Backend   | Python, FastAPI, Uvicorn, Pydantic  |
| AI        | OpenRouter API (DeepSeek model)     |
| Security  | SlowAPI (rate limiting), python-dotenv |

---

## ⚙️ Setup

### Backend

```bash
cd backend

# 1. Create and activate a virtual environment (recommended)
python -m venv venv
.\venv\Scripts\Activate.ps1    # Windows
# source venv/bin/activate     # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create your .env
copy .env.example .env         # Windows
# cp .env.example .env         # macOS/Linux

# 4. Add your OpenRouter API key to .env
# OPENROUTER_API_KEY=sk-or-v1-...
# Get a free key at https://openrouter.ai/keys
```

### Frontend

```bash
cd frontend

# 1. Install dependencies
npm install

# 2. Create .env.local
copy .env.local.example .env.local
# (default NEXT_PUBLIC_API_URL=http://localhost:8000 is fine for local dev)
```

---

## ▶️ Running Locally

Open **two terminals**:

**Terminal 1 — Backend**
```bash
cd backend
python -m uvicorn main:app --reload
# → http://localhost:8000
# → http://localhost:8000/docs  (Swagger UI)
```

**Terminal 2 — Frontend**
```bash
cd frontend
npm run dev
# → http://localhost:3000
```

Open **http://localhost:3000** in your browser.

---

## 🧪 How to Use

1. Paste or write code in the Monaco editor (language is auto-detected)
2. Or **upload a file**, **load from GitHub**, or **submit a PR URL**
3. Click **⚡ Analyze Code**
4. View the AI review:
   - 🐛 **Bug Detection** — with severity (high/medium/low) and fix suggestions
   - ⏱️ **Time Complexity** — Big-O analysis
   - 💾 **Space Complexity** — Big-O analysis
   - ⚡ **Performance Improvements**
   - ✨ **Clean Code Suggestions**
   - 📋 **Overall Summary**
   - 💡 **AI-Generated Optimized Code** — copy-ready improved version

---

## 🔌 API Reference

### `GET /`
```json
{ "status": "ok", "message": "AI Code Review Assistant API", "model": "deepseek/deepseek-chat", "ready": true }
```

### `POST /review` *(rate limited: 5/min)*
**Request:**
```json
{ "code": "def find_max(lst): ...", "language": "python" }
```
**Response:**
```json
{
  "status": "success",
  "language": "python",
  "model_used": "deepseek/deepseek-chat",
  "bugs": [{ "line": "2", "description": "...", "severity": "high", "suggestion": "..." }],
  "time_complexity": "O(n²) — ...",
  "space_complexity": "O(1) — ...",
  "optimizations": ["Use Python's built-in max()", "..."],
  "clean_code": ["Rename lst to numbers", "..."],
  "overall_summary": "...",
  "optimized_code": "def find_max(numbers): ..."
}
```

### `POST /fetch/github`
**Request:**
```json
{ "url": "https://github.com/owner/repo/blob/main/file.py", "github_token": null }
```

### `POST /review/pr` *(rate limited: 5/min)*
**Request:**
```json
{ "pr_url": "https://github.com/owner/repo/pull/123", "github_token": null }
```

---

## 🚀 Deployment

### Frontend → Vercel

```bash
cd frontend
npm install -g vercel
vercel --prod
```
Set environment variable in Vercel dashboard:
```
NEXT_PUBLIC_API_URL=https://your-backend.onrender.com
```

### Backend → Render

1. Create a new **Web Service** on [render.com](https://render.com)
2. Root directory: `backend`
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. Add environment variable: `OPENROUTER_API_KEY=your_key`

---

## 🔒 Security Notes

- Never commit `.env` — it is in `.gitignore`
- Rate limited to 5 req/min per IP to prevent abuse
- In production, restrict CORS `allow_origins` to your actual frontend domain
- Use environment secrets (Vercel/Render dashboards) instead of committed files

---

## 👨‍💻 Developer

Built by **[Suyash Singh](https://www.linkedin.com/in/suyash-singh-4b616a324)**
