# 🤖 AI Code Review Assistant

A full-stack production-ready application that lets you paste code, send it to **Google Gemini**, and receive a detailed structured review — bugs, time/space complexity, optimizations, and clean code suggestions.

---

## 📁 Project Structure

```
ai-code-review-assistant/
├── backend/
│   ├── main.py          # FastAPI app + endpoints
│   ├── llm_service.py   # Gemini API client + prompt builder
│   ├── models.py        # Pydantic request/response models
│   ├── requirements.txt
│   ├── .env             # Your secrets (not committed)
│   └── .env.example
└── frontend/
    ├── components/
    │   ├── CodeEditor.jsx   # Monaco editor (VS Code)
    │   └── ReviewPanel.jsx  # Structured review display
    ├── pages/
    │   ├── _app.js
    │   └── index.js         # Main split-pane layout
    ├── styles/
    │   └── globals.css
    ├── package.json
    ├── tailwind.config.js
    └── .env.local.example
```

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

# 4. Add your Gemini API key to .env
# GEMINI_API_KEY=AIzaSy...
# Get a key at https://aistudio.google.com/apikey
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

1. Select a programming language (Python, C++, JavaScript, Java)
2. Paste or write code in the Monaco editor
3. Click **⚡ Analyze Code**
4. View the AI review:
   - 🐛 **Bug Detection** — with severity (high/medium/low) and fix suggestions
   - ⏱️ **Time Complexity** — Big-O analysis
   - 💾 **Space Complexity** — Big-O analysis
   - ⚡ **Performance Improvements**
   - ✨ **Clean Code Suggestions**
   - 📋 **Overall Summary**

---

## 🔌 API Reference

### `GET /`
```json
{ "message": "AI Code Review Assistant API", "ready": true, "model": "gemini-2.0-flash-lite" }
```

### `POST /review`
**Request:**
```json
{ "code": "def find_max(lst): ...", "language": "python" }
```
**Response:**
```json
{
  "status": "success",
  "language": "python",
  "model_used": "gemini-2.0-flash-lite",
  "bugs": [{ "line": "2", "description": "...", "severity": "high", "suggestion": "..." }],
  "time_complexity": "O(n²) — ...",
  "space_complexity": "O(1) — ...",
  "optimizations": ["Use Python's built-in max()", "..."],
  "clean_code": ["Rename lst to numbers", "..."],
  "overall_summary": "..."
}
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
5. Add environment variable: `GEMINI_API_KEY=your_key`

---

## 🔒 Security Notes

- Never commit `.env` — it is in `.gitignore`
- In production, restrict CORS `allow_origins` to your actual frontend domain
- Use environment secrets (Vercel/Render dashboards) instead of committed files
