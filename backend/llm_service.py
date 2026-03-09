"""
llm_service.py — OpenRouter / DeepSeek AI integration layer
============================================================
Handles all communication with the LLM:

  • Environment variable loading via python-dotenv
  • Safe API key validation at startup
  • Structured prompt construction
  • Code truncation to stay within token limits (6000 chars)
  • Async HTTP via httpx with streaming support
  • Retry logic: 3 retries with 5-second delays on 429 errors
  • JSON response parsing with fallback handling

Provider:  OpenRouter  (https://openrouter.ai)
Model:     DeepSeek    (deepseek/deepseek-chat)
"""

import os
import json
import asyncio
import logging

import httpx
from dotenv import load_dotenv

from models import BugReport, CodeReviewResponse, CPDebugResponse

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
# 6000 chars gives the model enough context for accurate reviews
# while staying within reasonable token limits.
MAX_CODE_LENGTH: int = 6000

# Retry settings for 429 RESOURCE_EXHAUSTED / rate-limit errors
RETRY_WAIT_SECONDS: int = 5
MAX_RETRIES: int = 3

# HTTP request timeout (seconds)
REQUEST_TIMEOUT: int = 45

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
You are a senior software engineer performing a precise, professional code review.

RESPOND ONLY WITH A VALID JSON OBJECT. No markdown fences, no commentary, no text outside the JSON.

Required JSON schema:
{
  "bugs": [
    {
      "line":        "<exact line number or range (e.g. '5' or '12-15'), or null if not applicable>",
      "description": "<clear, specific description of the bug>",
      "severity":    "<low | medium | high>",
      "suggestion":  "<actionable fix with a code snippet if helpful>"
    }
  ],
  "time_complexity":  "<Big-O with a one-line explanation, e.g. 'O(n^2) — nested loop over the input array'>",
  "space_complexity": "<Big-O with a one-line explanation>",
  "optimizations":    ["<specific, actionable performance improvement>"],
  "clean_code":       ["<specific readability / naming / style improvement>"],
  "overall_summary":  "<2-3 sentence summary: what works well, what's critical to fix, overall quality rating>",
  "optimized_code":   "<complete, runnable rewritten version with ALL bugs fixed and improvements applied — code only, no explanations>"
}

Severity guidelines:
- high: crashes, data loss, security vulnerabilities, infinite loops, wrong results
- medium: edge-case failures, resource leaks, poor error handling, race conditions
- low: style issues, minor inefficiencies, missing documentation

Rules:
- Return [] for bugs if none found.
- Always reference actual variable/function names and exact line numbers.
- In optimized_code: return complete, runnable, improved code — not a partial snippet.
- Be concise. Do not pad arrays with filler items.
""".strip()

# ── PR review system prompt ──────────────────────────────────────────────────
PR_SYSTEM_INSTRUCTION = """
You are a senior software engineer reviewing a GitHub Pull Request diff.

The input is a unified diff (patch format). Focus on bugs and issues INTRODUCED by the changes, not pre-existing code.

RESPOND ONLY WITH A VALID JSON OBJECT. No markdown fences, no commentary.

Required JSON schema:
{
  "bugs": [
    {
      "line":        "<filename:line or line range in the diff>",
      "description": "<bug introduced or revealed by this change>",
      "severity":    "<low | medium | high>",
      "suggestion":  "<actionable fix>"
    }
  ],
  "time_complexity":  "<impact of the changed code on time complexity>",
  "space_complexity": "<impact of the changed code on space complexity>",
  "optimizations":    ["<improvement the PR should make>"],
  "clean_code":       ["<code style / readability issue in the diff>"],
  "overall_summary":  "<2-3 sentence summary: is this PR safe to merge? key concerns?>",
  "optimized_code":   "<improved version of the most important changed file, or empty string>"
}

Severity guidelines:
- high: crashes, data loss, security vulnerabilities, wrong results
- medium: edge-case failures, resource leaks, poor error handling
- low: style issues, minor inefficiencies

Rules:
- Focus only on code in + (added) lines. Don't flag deleted code.
- Return [] for bugs if the PR is clean.
- Be concise and actionable.
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
#  Async HTTP client (reused across requests for connection pooling)
# =============================================================================

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    """Lazy-initialize a shared async HTTP client for connection pooling."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
    return _http_client


# =============================================================================
#  Helper: call OpenRouter with retry on 429 (async + streaming)
# =============================================================================

async def _call_llm_with_retry(
    system_prompt: str,
    user_prompt: str,
) -> str:
    """
    Sends an async streaming chat completion request to OpenRouter.

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
        "top_p": 0.95,                # Slightly constrain sampling for consistency
        "max_tokens": 2048,           # Cap output length for faster generation
        "stream": True,               # Stream tokens for faster time-to-first-token
    }

    last_error: Exception | None = None
    client = _get_http_client()

    # ── Retry loop ───────────────────────────────────────────────────────────
    for attempt in range(1 + MAX_RETRIES):
        try:
            logger.info(
                "Calling OpenRouter (attempt %d/%d) | model=%s | stream=true",
                attempt + 1, 1 + MAX_RETRIES, LLM_MODEL,
            )

            # ── Streaming request ────────────────────────────────────────────
            async with client.stream(
                "POST",
                OPENROUTER_BASE_URL,
                headers=headers,
                json=payload,
            ) as resp:

                # ── 429: rate limited — retry after delay ────────────────────
                if resp.status_code == 429:
                    body = ""
                    async for chunk in resp.aiter_text():
                        body += chunk
                        if len(body) > 200:
                            break
                    last_error = RuntimeError(f"429 Rate Limited: {body[:200]}")
                    if attempt < MAX_RETRIES:
                        logger.warning(
                            "429 rate limited — waiting %ds before retry (%d/%d).",
                            RETRY_WAIT_SECONDS, attempt + 1, MAX_RETRIES,
                        )
                        await asyncio.sleep(RETRY_WAIT_SECONDS)
                        continue
                    else:
                        logger.error("429 rate limited — all %d retries exhausted.", MAX_RETRIES)
                        break

                # ── Other HTTP errors — fail immediately ─────────────────────
                if resp.status_code >= 400:
                    body = ""
                    async for chunk in resp.aiter_text():
                        body += chunk
                        if len(body) > 300:
                            break
                    logger.error("OpenRouter error %d: %s", resp.status_code, body[:300])
                    raise RuntimeError(
                        f"OpenRouter API error {resp.status_code}: {body[:300]}"
                    )

                # ── Success — collect streamed SSE chunks ────────────────────
                collected_content = []
                async for line in resp.aiter_lines():
                    # SSE format: "data: {...}"
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]  # strip "data: " prefix
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                        delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                        token = delta.get("content", "")
                        if token:
                            collected_content.append(token)
                    except json.JSONDecodeError:
                        continue  # skip malformed chunks

                content = "".join(collected_content)

                if not content.strip():
                    raise RuntimeError("Model returned empty response.")

                logger.info(
                    "LLM responded (%d chars) on attempt %d via streaming.",
                    len(content), attempt + 1,
                )
                return content

        except httpx.TimeoutException:
            last_error = RuntimeError(f"OpenRouter API timed out after {REQUEST_TIMEOUT}s.")
            logger.error("OpenRouter timed out on attempt %d.", attempt + 1)
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_WAIT_SECONDS)
                continue
            break

        except httpx.ConnectError as exc:
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
        f"Review the following {language} code. Provide:\n"
        f"1. Bug Detection (with exact line numbers)\n"
        f"2. Time & Space Complexity\n"
        f"3. Performance Improvements\n"
        f"4. Clean Code Suggestions\n"
        f"5. A fully rewritten optimised version\n\n"
        f"```{language}\n{safe_code}\n```"
    )


# =============================================================================
#  Public: review a code snippet (async)
# =============================================================================

async def get_code_review(language: str, code: str) -> CodeReviewResponse:
    """
    Main entry point for code reviews.
    1. Builds a structured prompt (with truncation)
    2. Calls OpenRouter/DeepSeek via async streaming (with retry on 429)
    3. Parses the JSON response into CodeReviewResponse
    """
    prompt = build_prompt(language, code)
    logger.info(
        "Starting code review | model=%s | language=%s | code_chars=%d",
        LLM_MODEL, language, len(code),
    )
    raw = await _call_llm_with_retry(SYSTEM_INSTRUCTION, prompt)
    return _parse_response(raw, language, LLM_MODEL)


# =============================================================================
#  Public: review a pull request diff (async)
# =============================================================================

async def get_pr_review(diff: str, pr_title: str, files_count: int) -> CodeReviewResponse:
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
    raw = await _call_llm_with_retry(PR_SYSTEM_INSTRUCTION, prompt)
    return _parse_response(raw, "diff", LLM_MODEL, pr_title=pr_title, files_reviewed=files_count)


# =============================================================================
#  Competitive Programming debug system prompt
# =============================================================================

CP_SYSTEM_INSTRUCTION = """
You are an expert competitive programming reviewer and debugger.

You are given:
1. The problem statement
2. The user's code
3. Sample I/O (expected vs actual)
4. **Code Execution Results** — the REAL output from running the code (trust this over the user's claimed output)
5. **Static Analysis** — automated pattern-based warnings about the code

Use ALL THREE sources (execution, static analysis, and your own reasoning) to provide the most accurate diagnosis.

RESPOND ONLY WITH A VALID JSON OBJECT. No markdown fences, no commentary, no text outside the JSON.

Required JSON schema:
{
  "what_is_wrong":    "<clear explanation of the bug(s) in the code>",
  "why_wrong_output": "<step-by-step trace showing why the code produces incorrect output>",
  "failing_test":     "<a specific test case (input) that causes the code to fail, with expected vs actual output>",
  "correct_approach": "<description of the correct algorithm / approach to solve the problem>",
  "corrected_code":   "<complete, runnable corrected version of the code>"
}

Rules:
- When execution results are available, use the REAL output — it's ground truth.
- Cross-reference static analysis warnings with your own reasoning.
- Be precise and reference exact variable names, line numbers, and logic errors.
- The failing_test must be concrete: show input, expected output, and actual output.
- The corrected_code must be complete and runnable — not a partial snippet.
- If the code is already correct, say so in what_is_wrong and return the original code as corrected_code.
- Be concise but thorough.
""".strip()


# =============================================================================
#  Public: debug a competitive programming solution (async)
# =============================================================================

async def get_cp_review(
    language: str,
    code: str,
    problem: str,
    sample_input: str,
    expected_output: str,
    actual_output: str,
    execution_stdout: str = "",
    execution_stderr: str = "",
    execution_status: str = "",
    static_analysis_text: str = "",
) -> CPDebugResponse:
    """
    Reviews a competitive programming solution using all three signals:
    1. Code execution results (ground truth)
    2. Static analysis warnings
    3. LLM reasoning

    Returns a CPDebugResponse with all fields populated.
    """
    safe_code = _truncate_code(code)

    # Build a rich prompt with all three data sources
    prompt_parts = [
        f"Problem Description:\n{problem}",
        f"\nUser Code ({language}):\n```{language}\n{safe_code}\n```",
        f"\nSample Input:\n{sample_input}" if sample_input else "",
        f"\nExpected Output:\n{expected_output}" if expected_output else "",
    ]

    # Execution results (ground truth)
    if execution_status:
        prompt_parts.append(f"\n--- Code Execution Results (ground truth) ---")
        prompt_parts.append(f"Execution Status: {execution_status}")
        if execution_stdout:
            prompt_parts.append(f"Actual stdout:\n{execution_stdout}")
        if execution_stderr:
            prompt_parts.append(f"Stderr:\n{execution_stderr}")
        if actual_output and execution_stdout.strip() != actual_output.strip():
            prompt_parts.append(f"(User-reported actual output: {actual_output})")
    elif actual_output:
        prompt_parts.append(f"\nActual Output (user-reported, not verified):\n{actual_output}")

    # Static analysis
    if static_analysis_text:
        prompt_parts.append(f"\n--- {static_analysis_text} ---")

    prompt_parts.append(
        "\nUsing the execution results, static analysis, and your own reasoning, explain:\n"
        "1. What is wrong in the code\n"
        "2. Why it produces incorrect output\n"
        "3. Provide a failing test case\n"
        "4. Suggest the correct approach\n"
        "5. Provide a complete corrected version of the code"
    )

    prompt = "\n".join(p for p in prompt_parts if p)

    logger.info(
        "Starting CP debug review | model=%s | language=%s | code_chars=%d | has_execution=%s | has_analysis=%s",
        LLM_MODEL, language, len(code), bool(execution_status), bool(static_analysis_text),
    )
    raw = await _call_llm_with_retry(CP_SYSTEM_INSTRUCTION, prompt)
    return _parse_cp_response(raw, language, LLM_MODEL)


# =============================================================================
#  Helper: parse CP debug response
# =============================================================================

def _parse_cp_response(raw: str, language: str, model: str) -> CPDebugResponse:
    """Parses the raw JSON string from the LLM into a CPDebugResponse."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n") if "\n" in cleaned else len(cleaned)
        cleaned = cleaned[first_newline + 1:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()

    try:
        data: dict = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON from LLM (CP): %s\nRaw:\n%s", exc, raw[:500])
        raise RuntimeError("Model returned invalid JSON.") from exc

    return CPDebugResponse(
        language=language,
        model_used=model,
        what_is_wrong=data.get("what_is_wrong", ""),
        why_wrong_output=data.get("why_wrong_output", ""),
        failing_test=data.get("failing_test", ""),
        correct_approach=data.get("correct_approach", ""),
        corrected_code=data.get("corrected_code", ""),
    )
