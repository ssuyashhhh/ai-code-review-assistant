"""
models.py — Pydantic request / response schemas
=================================================
Defines the data contracts between frontend and backend.
All validation happens here via Pydantic so the endpoint handlers stay clean.
"""
from pydantic import BaseModel, Field


# =============================================================================
#  Code Review — request & response
# =============================================================================

class CodeReviewRequest(BaseModel):
    """
    Incoming body for POST /review.
    - code:     the source code to review (min 1 char, will be truncated if too long)
    - language: the programming language (e.g. python, cpp, javascript, java)
    """
    code: str = Field(..., min_length=1, description="Source code to review.")
    language: str = Field(
        ..., min_length=1,
        description="Programming language (e.g. python, javascript, typescript, java, c, cpp, csharp, go, rust, ruby, php, swift, kotlin, scala, dart, r, sql, shell, perl, lua, haskell, html, css).",
    )


class BugReport(BaseModel):
    """A single bug found during the review."""
    line:        str | None = Field(None, description="Line number / range or null.")
    description: str        = Field(..., description="What the bug is.")
    severity:    str        = Field(..., description="low | medium | high")
    suggestion:  str        = Field(..., description="How to fix it.")


class CodeReviewResponse(BaseModel):
    """
    Full structured code review returned by /review and /review/pr.
    Every field has a safe default so the frontend never crashes on missing data.
    """
    status:           str            = "success"
    language:         str
    model_used:       str
    bugs:             list[BugReport]
    time_complexity:  str
    space_complexity: str
    optimizations:    list[str]
    clean_code:       list[str]
    overall_summary:  str
    optimized_code:   str = ""       # Complete rewritten code with all improvements
    # PR-specific fields (populated only for /review/pr)
    pr_title:         str | None = None
    files_reviewed:   int | None = None


# =============================================================================
#  GitHub File Fetch
# =============================================================================

class GithubFetchRequest(BaseModel):
    """Incoming body for POST /fetch/github."""
    url:          str        = Field(..., description="GitHub blob URL")
    github_token: str | None = Field(None, description="PAT for private repos (optional).")


class GithubFetchResponse(BaseModel):
    """Response from POST /fetch/github."""
    code:     str
    language: str
    filename: str


# =============================================================================
#  Pull Request Review
# =============================================================================

class PRReviewRequest(BaseModel):
    """Incoming body for POST /review/pr."""
    pr_url:       str        = Field(..., description="https://github.com/owner/repo/pull/123")
    github_token: str | None = Field(None, description="PAT for private repos (optional).")
