"""
main.py — FastAPI application entry point
==========================================
REST API for the AI Code Review Assistant.

Endpoints:
  • GET  /             → health check
  • POST /review       → analyse a code snippet (rate limited: 5 req/min/IP)
  • POST /fetch/github → fetch a file from a GitHub blob URL
  • POST /review/pr    → review a GitHub Pull Request diff
  • POST /review/cp    → debug a competitive programming solution

Security features:
  • SlowAPI rate limiting (5 req/min per IP on /review)
  • Input truncation (6000 chars max in llm_service)
  • Retry logic (3 retries, 5s delay on 429 errors)
  • Structured error responses { status: "error", message: "..." }
"""

import logging

# ── Logging setup (before other imports so library logs are captured) ─────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  [%(levelname)s]  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── SlowAPI rate limiting ────────────────────────────────────────────────────
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# ── Local imports ────────────────────────────────────────────────────────────
from models import (
    CodeReviewRequest, CodeReviewResponse,
    GithubFetchRequest, GithubFetchResponse,
    PRReviewRequest, CPDebugRequest,
)
from llm_service import get_code_review, get_pr_review, get_cp_review, LLM_MODEL, OPENROUTER_API_KEY
from github_service import fetch_github_file, fetch_pr_diff
from code_executor import execute_code
from static_analyzer import analyze as static_analyze, format_for_prompt as format_analysis


# =============================================================================
#  SlowAPI setup
# =============================================================================
limiter = Limiter(key_func=get_remote_address)


# =============================================================================
#  FastAPI app
# =============================================================================
app = FastAPI(
    title="AI Code Review Assistant",
    description="Code review powered by OpenRouter (DeepSeek). Rate limited.",
    version="3.0.0",
)

# ── Attach SlowAPI to the app ────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS middleware ──────────────────────────────────────────────────────────
# IMPORTANT: must be added AFTER exception handlers so it wraps everything.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # Allow all origins (safe for dev)
    allow_credentials=False,          # Must be False when using "*"
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
#  Guard: ensure the LLM API key is configured
# =============================================================================
def _require_llm():
    """Raises 503 if the OpenRouter API key was not set at startup."""
    if not OPENROUTER_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is not configured. Add it to backend/.env and restart.",
        )


# =============================================================================
#  GET / — health check
# =============================================================================
@app.get("/", tags=["Health"])
def root() -> dict:
    """Returns the API status, current model, and readiness."""
    return {
        "status": "ok",
        "message": "AI Code Review Assistant API",
        "version": "3.0.0",
        "model": LLM_MODEL,
        "ready": bool(OPENROUTER_API_KEY),
    }


# =============================================================================
#  POST /review — analyse a code snippet (RATE LIMITED)
# =============================================================================
#
#  IMPORTANT — SlowAPI parameter naming:
#  SlowAPI requires a parameter named exactly `request` that is an instance
#  of starlette.requests.Request. The Pydantic body is named `body` to avoid
#  the naming conflict.
#
@app.post("/review", tags=["Review"])
@limiter.limit("5/minute")
async def review_code(request: Request, body: CodeReviewRequest):
    """
    Accepts a code snippet + language, sends it to the LLM, returns a review.

    Rate limit: 5 requests per minute per client IP.
    """
    _require_llm()
    try:
        review = await get_code_review(body.language, body.code)
        return review
    except RuntimeError as exc:
        logging.error("Review failed (RuntimeError): %s", exc)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": str(exc)},
        )
    except Exception as exc:
        logging.error("Review failed (unexpected): %s", exc)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": "LLM request failed"},
        )


# =============================================================================
#  POST /fetch/github — fetch a file from GitHub
# =============================================================================
@app.post("/fetch/github", response_model=GithubFetchResponse, tags=["GitHub"])
def fetch_github(body: GithubFetchRequest) -> GithubFetchResponse:
    """Fetches a source file from a GitHub blob URL."""
    content, language, filename = fetch_github_file(body.url, body.github_token)
    return GithubFetchResponse(code=content, language=language, filename=filename)


# =============================================================================
#  POST /review/pr — review a pull request (RATE LIMITED)
# =============================================================================
@app.post("/review/pr", tags=["GitHub"])
@limiter.limit("5/minute")
async def review_pr(request: Request, body: PRReviewRequest):
    """
    Fetches a GitHub PR's diff, sends it to the LLM for review.

    Rate limit: 5 requests per minute per client IP.
    """
    _require_llm()
    diff, pr_title, files_count = fetch_pr_diff(body.pr_url, body.github_token)
    try:
        review = await get_pr_review(diff, pr_title, files_count)
        return review
    except RuntimeError as exc:
        logging.error("PR review failed (RuntimeError): %s", exc)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": str(exc)},
        )
    except Exception as exc:
        logging.error("PR review failed (unexpected): %s", exc)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": "LLM request failed"},
        )


# =============================================================================
#  POST /review/cp — debug a competitive programming solution (RATE LIMITED)
# =============================================================================
@app.post("/review/cp", tags=["Review"])
@limiter.limit("5/minute")
async def review_cp(request: Request, body: CPDebugRequest):
    """
    Debugs a competitive programming solution using three signals:
    1. Code Execution — runs the code with sample input (ground truth)
    2. Static Analysis — pattern-based detection of common CP bugs
    3. LLM Reasoning — DeepSeek analyzes everything together

    Rate limit: 5 requests per minute per client IP.
    """
    _require_llm()
    try:
        # ── Step 1: Execute the code with sample input ───────────────
        exec_result = execute_code(body.language, body.code, body.sample_input)
        if exec_result.executed:
            execution_status = "success" if not exec_result.error else exec_result.error
            if exec_result.timed_out:
                execution_status = "Time Limit Exceeded"
        else:
            execution_status = f"skipped: {exec_result.error}" if exec_result.error else "skipped"

        # ── Step 2: Run static analysis ──────────────────────────────
        analysis = static_analyze(body.language, body.code)
        analysis_text = format_analysis(analysis)
        analysis_warnings = [
            f"[{w.severity.upper()}] Line {w.line or '?'} — {w.category}: {w.message}"
            for w in analysis.warnings
        ]

        # ── Step 3: LLM reasoning (with execution + analysis context) ─
        review = await get_cp_review(
            body.language,
            body.code,
            body.problem,
            body.sample_input,
            body.expected_output,
            body.actual_output,
            execution_stdout=exec_result.stdout,
            execution_stderr=exec_result.stderr,
            execution_status=execution_status,
            static_analysis_text=analysis_text,
        )

        # Attach execution + analysis results to the response
        review.execution_stdout = exec_result.stdout
        review.execution_stderr = exec_result.stderr
        review.execution_status = execution_status
        review.static_analysis = analysis_warnings

        return review
    except RuntimeError as exc:
        logging.error("CP review failed (RuntimeError): %s", exc)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": str(exc)},
        )
    except Exception as exc:
        logging.error("CP review failed (unexpected): %s", exc)
        return JSONResponse(
            status_code=502,
            content={"status": "error", "message": "LLM request failed"},
        )
