"""
llm_service.py — OpenRouter / DeepSeek AI integration layer
============================================================
Handles all communication with the LLM:

  • Environment variable loading via python-dotenv
  • Safe API key validation at startup
  • Structured prompt construction
  • Code truncation to stay within free-tier token limits (3000 chars)
  • Retry logic: 3 retries with 20-second delays on 429 errors
  • JSON response parsing with fallback handling

Provider:  OpenRouter  (https://openrouter.ai)
Model:     DeepSeek    (deepseek/deepseek-chat)
"""

import os
import json
import time
import logging

import requests as http_client          # renamed to avoid conflict with FastAPI
from dotenv import load_dotenv

from models import BugReport, CodeReviewResponse

# ── Load .env into os.environ ────────────────────────────────────────────────
# Must happen before reading any environment variables.
load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
#  Configuration — loaded once at startup
# =============================================================================

# OpenRouter API key — required
OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")

# Model to use via OpenRouter (DeepSeek is fast, cheap, and capable)
LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek/deepseek-chat")

# OpenRouter API endpoint (OpenAI-compatible)
OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"

# Max characters sent to the model.
# Truncating to 3000 chars prevents hitting token limits on the free tier.
MAX_CODE_LENGTH: int = 3000

# Retry settings for 429 RESOURCE_EXHAUSTED / rate-limit errors
RETRY_WAIT_SECONDS: int = 20
MAX_RETRIES: int = 3

# ── Validate API key at startup ──────────────────────────────────────────────
if OPENROUTER_API_KEY:
    logger.info("OpenRouter API key loaded  (model: %s)", LLM_MODEL)
else:
    logger.warning(
        "OPENROUTER_API_KEY is not set. "
        "Add it to backend/.env and restart. /review will return 503."
    )


# =============================================================================
#  System instructions (sent as the "system" message)
# =============================================================================

# ── Code review system prompt ────────────────────────────────────────────────
SYSTEM_INSTRUCTION = """
You are a senior software engineer performing a professional code review.

Respond ONLY with a valid JSON object — no markdown fences, no text outside the JSON.

Schema:
{
  "bugs": [
    {
      "line":        "<line number or range, or null>",
      "description": "<what the bug is>",
      "severity":    "<low | medium | high>",
      "suggestion":  "<how to fix it>"
    }
  ],
  "time_complexity":  "<Big-O analysis with brief explanation>",
  "space_complexity": "<Big-O analysis with brief explanation>",
  "optimizations":    ["<performance improvement 1>", "..."],
  "clean_code":       ["<readability / naming improvement 1>", "..."],
  "overall_summary":  "<2-3 sentence summary of quality and top priorities>",
  "optimized_code":   "<complete rewritten version of the code with ALL improvements applied — fix all bugs, optimizations, and clean code suggestions. Return ONLY the code, no explanations inside this field>"
}

Rules:
- Return empty array [] for bugs if none found.
- Reference actual variable names and line numbers where possible.
- In optimized_code: return a complete, runnable, improved version.
""".strip()

# ── PR review system prompt ──────────────────────────────────────────────────
PR_SYSTEM_INSTRUCTION = """
You are a senior software engineer reviewing a GitHub Pull Request diff.

The input is a unified diff (patch format). Analyze the changes and respond ONLY with a valid JSON object.

Schema:
{
  "bugs": [
    {
      "line":        "<line number or filename reference>",
      "description": "<bug introduced or revealed by this PR>",
      "severity":    "<low | medium | high>",
      "suggestion":  "<how to fix it>"
    }
  ],
  "time_complexity":  "<impact of the changed code on time complexity>",
  "space_complexity": "<impact of the changed code on space complexity>",
  "optimizations":    ["<improvement the PR could make>", "..."],
  "clean_code":       ["<code style / readability issue in the diff>", "..."],
  "overall_summary":  "<2-3 sentence summary of PR quality and key feedback>",
  "optimized_code":   "<suggested improved version of the most important changed file, or empty string>"
}
""".strip()


# =============================================================================
#  Helper: truncate code to stay within token limits
# =============================================================================

def _truncate_code(code: str, max_len: int = MAX_CODE_LENGTH) -> str:
    """
    Truncate code to `max_len` characters.
    Appends a marker so the model knows the input was cut short.
    """
    if len(code) <= max_len:
        return code
    logger.info("Truncating code from %d to %d chars.", len(code), max_len)
    return code[:max_len] + "\n\n// ... [truncated to stay within token limits]"


# =============================================================================
#  Helper: call OpenRouter with retry on 429
# =============================================================================

def _call_llm_with_retry(
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Sends a chat completion request to OpenRouter.

    Retry logic:
      • If the API returns 429 (rate limited), wait RETRY_WAIT_SECONDS and retry.
      • Up to MAX_RETRIES total retries (so up to 4 attempts total).
      • Non-429 errors fail immediately.

    Returns:
        The raw text content from the model's response.

    Raises:
        RuntimeError on permanent failure.
    """
    # ── Guard: ensure key is configured ──────────────────────────────────────
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not set — check backend/.env")

    # ── Build the request payload (OpenAI-compatible) ────────────────────────
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:3000",      # Required by OpenRouter
        "X-Title": "AI Code Review Assistant",         # App name for OpenRouter dashboard
    }

    payload = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "temperature": 0.2,           # Low temp = deterministic reviews
        "max_tokens": 4096,
    }

    last_error: Exception | None = None

    # ── Retry loop ───────────────────────────────────────────────────────────
    for attempt in range(1 + MAX_RETRIES):
        try:
            logger.info(
                "Calling OpenRouter (attempt %d/%d) | model=%s",
                attempt + 1, 1 + MAX_RETRIES, LLM_MODEL,
            )

            resp = http_client.post(
                OPENROUTER_BASE_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )

            # ── 429: rate limited — retry after delay ────────────────────────
            if resp.status_code == 429:
                last_error = RuntimeError(f"429 Rate Limited: {resp.text[:200]}")
                if attempt < MAX_RETRIES:
                    logger.warning(
                        "429 rate limited — waiting %ds before retry (%d/%d).",
                        RETRY_WAIT_SECONDS, attempt + 1, MAX_RETRIES,
                    )
                    time.sleep(RETRY_WAIT_SECONDS)
                    continue
                else:
                    logger.error("429 rate limited — all %d retries exhausted.", MAX_RETRIES)
                    break

            # ── Other HTTP errors — fail immediately ─────────────────────────
            if not resp.ok:
                error_body = resp.text[:300]
                logger.error("OpenRouter error %d: %s", resp.status_code, error_body)
                raise RuntimeError(
                    f"OpenRouter API error {resp.status_code}: {error_body}"
                )

            # ── Success — extract the message content ────────────────────────
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            logger.info("LLM responded (%d chars) on attempt %d.", len(content), attempt + 1)
            return content

        except http_client.exceptions.Timeout:
            last_error = RuntimeError("OpenRouter API timed out after 60s.")
            logger.error("OpenRouter timed out on attempt %d.", attempt + 1)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            break

        except http_client.exceptions.ConnectionError as exc:
            last_error = RuntimeError(f"Connection error: {exc}")
            logger.error("Connection error on attempt %d: %s", attempt + 1, exc)
            break   # Connection errors are not retryable

    raise RuntimeError(f"LLM request failed after {MAX_RETRIES} retries: {last_error}")


# =============================================================================
#  Helper: parse LLM JSON response
# =============================================================================

def _parse_response(
    raw: str,
    language: str,
    model: str,
    pr_title: str | None = None,
    files_reviewed: int | None = None,
) -> CodeReviewResponse:
    """
    Parses the raw JSON string from the LLM into a validated CodeReviewResponse.
    Falls back to safe defaults for any missing fields.

    Some models wrap JSON in ```json ... ``` fences — we strip those first.
    """
    # ── Strip markdown code fences if present ────────────────────────────────
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # Remove opening fence (```json or ```)
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    # ── Parse JSON ───────────────────────────────────────────────────────────
    try:
        data: dict = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from LLM: %s\nRaw:\n%s", exc, raw[:500])
        raise RuntimeError("Model returned invalid JSON.") from exc

    # ── Build response with safe defaults ────────────────────────────────────
    return CodeReviewResponse(
        language=language,
        model_used=model,
        bugs=[BugReport(**b) for b in data.get("bugs", [])],
        time_complexity=data.get("time_complexity", "Not analysed."),
        space_complexity=data.get("space_complexity", "Not analysed."),
        optimizations=data.get("optimizations", []),
        clean_code=data.get("clean_code", []),
        overall_summary=data.get("overall_summary", ""),
        optimized_code=data.get("optimized_code", ""),
        pr_title=pr_title,
        files_reviewed=files_reviewed,
    )


# =============================================================================
#  Public: build a structured prompt
# =============================================================================

def build_prompt(language: str, code: str) -> str:
    """
    Constructs the user-turn prompt for a code review.
    The code is truncated to MAX_CODE_LENGTH before embedding.
    """
    safe_code = _truncate_code(code)
    return (
        f"Analyze the following code and provide:\n"
        f"1. Bug Detection\n"
        f"2. Time Complexity\n"
        f"3. Space Complexity\n"
        f"4. Performance Improvements\n"
        f"5. Clean Code Suggestions\n"
        f"6. A fully rewritten optimised version\n\n"
        f"Programming Language: {language}\n\n"
        f"Code:\n```{language}\n{safe_code}\n```"
    )


# =============================================================================
#  Public: review a code snippet
# =============================================================================

def get_code_review(language: str, code: str) -> CodeReviewResponse:
    """
    Main entry point for code reviews.
    1. Builds a structured prompt (with truncation)
    2. Calls OpenRouter/DeepSeek (with retry on 429)
    3. Parses the JSON response into CodeReviewResponse
    """
    prompt = build_prompt(language, code)
    logger.info(
        "Starting code review | model=%s | language=%s | code_chars=%d",
        LLM_MODEL, language, len(code),
    )
    raw = _call_llm_with_retry(SYSTEM_INSTRUCTION, prompt)
    return _parse_response(raw, language, LLM_MODEL)


# =============================================================================
#  Public: review a pull request diff
# =============================================================================

def get_pr_review(diff: str, pr_title: str, files_count: int) -> CodeReviewResponse:
    """
    Reviews a GitHub PR diff.
    The diff is truncated to MAX_CODE_LENGTH * 2 (diffs are naturally larger).
    """
    safe_diff = _truncate_code(diff, max_len=MAX_CODE_LENGTH * 2)
    prompt = (
        f"Review this Pull Request: \"{pr_title}\"\n"
        f"Files changed: {files_count}\n\n"
        f"Diff:\n{safe_diff}"
    )
    logger.info("Starting PR review | title=%s | diff_chars=%d", pr_title, len(safe_diff))
    raw = _call_llm_with_retry(PR_SYSTEM_INSTRUCTION, prompt)
    return _parse_response(raw, "diff", LLM_MODEL, pr_title=pr_title, files_reviewed=files_count)
