"""
=============================================================================
  AI Code Review Assistant — Backend
  File   : main.py
  Version: 3.0.0
  Desc   : FastAPI server that receives source code, sends it to Google Gemini,
           and returns a structured code review covering:
             * Bug detection
             * Time complexity analysis
             * Optimization suggestions
             * Clean code improvements
=============================================================================
"""

import os
import logging
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from google import genai
from google.genai import types

# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD ENVIRONMENT VARIABLES
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL:   str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ─────────────────────────────────────────────────────────────────────────────
# 2. CONFIGURE LOGGING
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# 3. GEMINI CLIENT
#    google-genai >= 1.0 uses genai.Client() instead of genai.configure().
#    The client is created once at startup and reused across all requests.
# ─────────────────────────────────────────────────────────────────────────────
gemini_client: genai.Client | None = None

if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    logger.info("Gemini client initialised (model: %s)", GEMINI_MODEL)
else:
    logger.warning(
        "GEMINI_API_KEY not set. POST /review will return 503 until "
        "the key is added to .env and the server is restarted."
    )

# ─────────────────────────────────────────────────────────────────────────────
# 4. FASTAPI APP
# ─────────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Code Review Assistant",
    description=(
        "Accepts source code and returns a structured Gemini-powered review: "
        "bugs, time complexity, optimisation suggestions, and clean-code tips."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Tighten to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# 5. PYDANTIC MODELS
# ─────────────────────────────────────────────────────────────────────────────

class CodeReviewRequest(BaseModel):
    """Request body for POST /review."""
    code: str = Field(
        ..., min_length=1,
        description="The source code to be reviewed.",
        examples=["def add(a, b):\n    return a + b"],
    )
    language: str = Field(
        ..., min_length=1,
        description="Programming language (e.g. 'python', 'cpp', 'javascript').",
        examples=["python"],
    )


class BugReport(BaseModel):
    """A single detected bug or potential error."""
    line:        str | None = Field(None, description="Line number or range, or null.")
    description: str        = Field(...,  description="What the bug is.")
    severity:    str        = Field(...,  description="'low', 'medium', or 'high'.")
    suggestion:  str        = Field(...,  description="How to fix it.")


class CodeReviewResponse(BaseModel):
    """Structured AI code review returned by POST /review."""
    status:          str            = "success"
    language:        str
    model_used:      str
    bugs:            list[BugReport]
    time_complexity: str
    optimizations:   list[str]
    clean_code:      list[str]
    overall_summary: str


# ─────────────────────────────────────────────────────────────────────────────
# 6. PROMPT
#    JSON mode is enforced by response_mime_type — the model MUST return valid
#    JSON. The system instruction describes the exact schema expected.
# ─────────────────────────────────────────────────────────────────────────────
SYSTEM_INSTRUCTION = """
You are an expert software engineer and code reviewer.

Respond ONLY with a valid JSON object matching this exact schema — no markdown, no prose outside the JSON:

{
  "bugs": [
    {
      "line":        "<line number / range, or null>",
      "description": "<what the bug is>",
      "severity":    "<low | medium | high>",
      "suggestion":  "<how to fix it>"
    }
  ],
  "time_complexity": "<Big-O analysis with explanation>",
  "optimizations": ["<concrete suggestion 1>", "..."],
  "clean_code":    ["<readability / naming improvement 1>", "..."],
  "overall_summary": "<2-3 sentence paragraph on quality and top priorities>"
}

Rules:
- If no bugs are found, return an empty array for "bugs".
- Reference actual variable names, line numbers, or patterns.
- Be specific and actionable — avoid generic advice.
""".strip()


def build_prompt(language: str, code: str) -> str:
    """Wraps the user's code in a prompt for Gemini."""
    return f"Review the following {language} code:\n\n```{language}\n{code}\n```"


# Generation config — JSON mode + low temperature for consistent output
GENERATION_CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_INSTRUCTION,
    temperature=0.2,
    max_output_tokens=2048,
    response_mime_type="application/json",  # Forces valid JSON output
)


# ─────────────────────────────────────────────────────────────────────────────
# 7. HEALTH-CHECK  GET /
# ─────────────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root() -> dict:
    """Returns server status and readiness."""
    return {
        "message": "AI Code Review Assistant is running",
        "version": "3.0.0",
        "model":   GEMINI_MODEL,
        "ready":   gemini_client is not None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. MAIN ENDPOINT  POST /review
# ─────────────────────────────────────────────────────────────────────────────
@app.post("/review", response_model=CodeReviewResponse, tags=["Code Review"])
def review_code(request: CodeReviewRequest) -> CodeReviewResponse:
    """
    Sends the submitted code to Google Gemini and returns a structured review.

    Covers:
    - **Bug detection** — logical errors, edge cases, potential exceptions.
    - **Time complexity** — Big-O analysis with explanation.
    - **Optimization suggestions** — concrete performance improvements.
    - **Clean code improvements** — readability, naming, structure.
    """

    # ── Guard: key must be configured ────────────────────────────────────────
    if gemini_client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini API key is not configured. "
                "Add GEMINI_API_KEY to your .env file and restart the server."
            ),
        )

    # ── Log incoming request ──────────────────────────────────────────────────
    logger.info(
        "Review request | language=%s | chars=%d",
        request.language, len(request.code),
    )

    # ── Call Gemini ───────────────────────────────────────────────────────────
    try:
        logger.info("Sending code to Gemini (%s)...", GEMINI_MODEL)
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=build_prompt(request.language, request.code),
            config=GENERATION_CONFIG,
        )
    except Exception as exc:
        logger.error("Gemini API error: %s", exc)
        raise HTTPException(status_code=502, detail=f"Gemini API error: {exc}") from exc

    # ── Parse JSON response ───────────────────────────────────────────────────
    raw: str = response.text or ""
    logger.info("Gemini response received (%d chars).", len(raw))

    try:
        data: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from Gemini: %s\nRaw:\n%s", exc, raw)
        raise HTTPException(
            status_code=500,
            detail="Gemini returned an invalid JSON response. Please try again.",
        ) from exc

    # ── Build and return structured response ──────────────────────────────────
    return CodeReviewResponse(
        language=request.language,
        model_used=GEMINI_MODEL,
        bugs=[BugReport(**b) for b in data.get("bugs", [])],
        time_complexity=data.get("time_complexity", "Not analysed."),
        optimizations=data.get("optimizations", []),
        clean_code=data.get("clean_code", []),
        overall_summary=data.get("overall_summary", ""),
    )
