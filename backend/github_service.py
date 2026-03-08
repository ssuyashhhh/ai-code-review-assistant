"""
github_service.py — fetch files and PR diffs from the GitHub API
"""
import re
import base64
import logging

import requests
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ── Language detection ────────────────────────────────────────────────────────
EXT_TO_LANG: dict[str, str] = {
    "py": "python", "cpp": "cpp", "cc": "cpp", "cxx": "cpp",
    "h": "cpp", "hpp": "cpp", "js": "javascript", "mjs": "javascript",
    "ts": "typescript", "java": "java", "go": "go", "rs": "rust",
    "rb": "ruby", "php": "php", "cs": "csharp",
    "swift": "swift", "kt": "kotlin",
}

def _detect_language(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXT_TO_LANG.get(ext, "plaintext")

def _headers(token: str | None = None) -> dict:
    h = {"Accept": "application/vnd.github.v3+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


# ── GitHub File ───────────────────────────────────────────────────────────────
def fetch_github_file(url: str, token: str | None = None) -> tuple[str, str, str]:
    """
    Fetch a single file from GitHub.
    `url` must be a blob URL: github.com/owner/repo/blob/branch/path/to/file

    Returns
    -------
    (content, language, filename)
    """
    m = re.search(r"github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)", url)
    if not m:
        raise HTTPException(
            status_code=422,
            detail=(
                "Invalid GitHub file URL. "
                "Expected: https://github.com/owner/repo/blob/branch/path/to/file.py"
            ),
        )
    owner, repo, branch, path = m.group(1), m.group(2), m.group(3), m.group(4)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}?ref={branch}"

    logger.info("Fetching GitHub file: %s/%s @ %s → %s", owner, repo, branch, path)

    try:
        resp = requests.get(api_url, headers=_headers(token), timeout=15)
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="GitHub API timed out.")

    if resp.status_code == 404:
        raise HTTPException(status_code=404,
            detail="File not found. Check the URL, branch name, and file path.")
    if resp.status_code == 403:
        raise HTTPException(status_code=403,
            detail="GitHub rate limit or access denied. Add a GitHub token for private repos.")
    if not resp.ok:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {resp.status_code}")

    data = resp.json()
    if data.get("type") != "file":
        raise HTTPException(status_code=422, detail="URL points to a directory, not a file.")

    content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
    filename = path.split("/")[-1]
    return content, _detect_language(filename), filename


# ── Pull Request Diff ─────────────────────────────────────────────────────────
def fetch_pr_diff(pr_url: str, token: str | None = None) -> tuple[str, str, int]:
    """
    Fetch the diff patches from a GitHub Pull Request.
    Capped at 15 files to stay within LLM context limits.

    Returns
    -------
    (diff_text, pr_title, files_count)
    """
    m = re.search(r"github\.com/([^/]+)/([^/]+)/pull/(\d+)", pr_url)
    if not m:
        raise HTTPException(
            status_code=422,
            detail="Invalid PR URL. Expected: https://github.com/owner/repo/pull/123",
        )
    owner, repo, pr_num = m.group(1), m.group(2), m.group(3)
    hdrs = _headers(token)
    base = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        # PR metadata
        pr_resp = requests.get(f"{base}/pulls/{pr_num}", headers=hdrs, timeout=15)
        if pr_resp.status_code == 404:
            raise HTTPException(status_code=404,
                detail="PR not found. Make sure it exists and the repo is public.")
        if pr_resp.status_code == 403:
            raise HTTPException(status_code=403,
                detail="GitHub rate limit or access denied. Provide a GitHub token.")
        pr_resp.raise_for_status()
        pr_title = pr_resp.json().get("title", f"PR #{pr_num}")

        # PR files
        files_resp = requests.get(f"{base}/pulls/{pr_num}/files", headers=hdrs, timeout=15)
        files_resp.raise_for_status()
        files = files_resp.json()

    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="GitHub API timed out.")

    diff_parts: list[str] = []
    for f in files[:15]:
        patch = f.get("patch", "")
        if patch:
            diff_parts.append(
                f"### {f.get('filename', '')}  [{f.get('status', '')}]\n{patch}"
            )

    if not diff_parts:
        raise HTTPException(
            status_code=422,
            detail="No reviewable diff found (PR may only contain binary files).",
        )

    return "\n\n".join(diff_parts), pr_title, len(files)
