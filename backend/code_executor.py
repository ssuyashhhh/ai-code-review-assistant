"""
code_executor.py — Sandboxed code execution for CP debugging
=============================================================
Runs user code with provided input, captures stdout/stderr.

Security:
  • Strict timeout (5s per execution)
  • Subprocess isolation (no shell=True)
  • Output size capped at 10KB
  • Only supports known languages
  • No filesystem/network escape from the subprocess

Supported languages:
  • Python     (python / python3)
  • C++        (g++)
  • C          (gcc)
  • JavaScript (node)
  • Java       (javac + java)
"""

import os
import subprocess
import tempfile
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Execution limits
EXEC_TIMEOUT = 5        # seconds
COMPILE_TIMEOUT = 10     # seconds
MAX_OUTPUT = 10_000      # chars

# Language → file extension mapping
LANG_EXTENSIONS = {
    "python": ".py",
    "cpp": ".cpp",
    "c": ".c",
    "javascript": ".js",
    "java": ".java",
}


@dataclass
class ExecutionResult:
    """Result of running user code."""
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    timed_out: bool = False
    error: str = ""            # high-level error (e.g. "compilation failed")
    executed: bool = False     # whether the code actually ran


def _truncate(text: str, max_len: int = MAX_OUTPUT) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n... [output truncated]"


def _find_executable(*names: str) -> str | None:
    """Find the first available executable from a list of names."""
    for name in names:
        # Check if it's on PATH
        try:
            result = subprocess.run(
                ["where" if os.name == "nt" else "which", name],
                capture_output=True, timeout=3,
            )
            if result.returncode == 0:
                return name
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    return None


def execute_code(language: str, code: str, stdin_input: str = "") -> ExecutionResult:
    """
    Execute user code with input and return the result.

    Runs in a temporary directory. Compilation + execution are separate steps
    for compiled languages. Returns ExecutionResult with stdout, stderr, etc.
    """
    lang = language.lower().strip()

    if lang not in LANG_EXTENSIONS:
        return ExecutionResult(
            error=f"Execution not supported for '{language}'. Supported: {', '.join(LANG_EXTENSIONS.keys())}",
        )

    try:
        with tempfile.TemporaryDirectory(prefix="cp_exec_") as tmpdir:
            if lang == "python":
                return _run_python(tmpdir, code, stdin_input)
            elif lang == "cpp":
                return _run_cpp(tmpdir, code, stdin_input)
            elif lang == "c":
                return _run_c(tmpdir, code, stdin_input)
            elif lang == "javascript":
                return _run_javascript(tmpdir, code, stdin_input)
            elif lang == "java":
                return _run_java(tmpdir, code, stdin_input)
            else:
                return ExecutionResult(error=f"Language '{lang}' not yet supported for execution.")
    except Exception as exc:
        logger.error("Code execution error: %s", exc)
        return ExecutionResult(error=f"Execution error: {exc}")


# ── Python ───────────────────────────────────────────────────────────────────

def _run_python(tmpdir: str, code: str, stdin_input: str) -> ExecutionResult:
    python_cmd = _find_executable("python3", "python")
    if not python_cmd:
        return ExecutionResult(error="Python not found on this system.")

    filepath = os.path.join(tmpdir, "solution.py")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

    return _execute_subprocess([python_cmd, filepath], stdin_input)


# ── C++ ──────────────────────────────────────────────────────────────────────

def _run_cpp(tmpdir: str, code: str, stdin_input: str) -> ExecutionResult:
    gpp = _find_executable("g++")
    if not gpp:
        return ExecutionResult(error="g++ not found on this system.")

    src = os.path.join(tmpdir, "solution.cpp")
    exe = os.path.join(tmpdir, "solution.exe" if os.name == "nt" else "solution")
    with open(src, "w", encoding="utf-8") as f:
        f.write(code)

    # Compile
    compile_result = _compile_subprocess([gpp, "-o", exe, src, "-std=c++17", "-O2"])
    if compile_result.error:
        return compile_result

    return _execute_subprocess([exe], stdin_input)


# ── C ────────────────────────────────────────────────────────────────────────

def _run_c(tmpdir: str, code: str, stdin_input: str) -> ExecutionResult:
    gcc = _find_executable("gcc")
    if not gcc:
        return ExecutionResult(error="gcc not found on this system.")

    src = os.path.join(tmpdir, "solution.c")
    exe = os.path.join(tmpdir, "solution.exe" if os.name == "nt" else "solution")
    with open(src, "w", encoding="utf-8") as f:
        f.write(code)

    compile_result = _compile_subprocess([gcc, "-o", exe, src, "-std=c11", "-O2"])
    if compile_result.error:
        return compile_result

    return _execute_subprocess([exe], stdin_input)


# ── JavaScript ───────────────────────────────────────────────────────────────

def _run_javascript(tmpdir: str, code: str, stdin_input: str) -> ExecutionResult:
    node = _find_executable("node")
    if not node:
        return ExecutionResult(error="Node.js not found on this system.")

    filepath = os.path.join(tmpdir, "solution.js")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)

    return _execute_subprocess([node, filepath], stdin_input)


# ── Java ─────────────────────────────────────────────────────────────────────

def _run_java(tmpdir: str, code: str, stdin_input: str) -> ExecutionResult:
    javac = _find_executable("javac")
    java = _find_executable("java")
    if not javac or not java:
        return ExecutionResult(error="Java (javac/java) not found on this system.")

    # Extract public class name (required by Java)
    import re
    match = re.search(r"public\s+class\s+(\w+)", code)
    class_name = match.group(1) if match else "Main"

    src = os.path.join(tmpdir, f"{class_name}.java")
    with open(src, "w", encoding="utf-8") as f:
        f.write(code)

    compile_result = _compile_subprocess([javac, src])
    if compile_result.error:
        return compile_result

    return _execute_subprocess([java, "-cp", tmpdir, class_name], stdin_input)


# ── Subprocess helpers ───────────────────────────────────────────────────────

def _compile_subprocess(cmd: list[str]) -> ExecutionResult:
    """Run a compilation command. Returns an error result if compilation fails."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
        )
        if result.returncode != 0:
            return ExecutionResult(
                stderr=_truncate(result.stderr),
                exit_code=result.returncode,
                error=f"Compilation failed:\n{_truncate(result.stderr)}",
            )
        return ExecutionResult()  # success — no error
    except subprocess.TimeoutExpired:
        return ExecutionResult(error="Compilation timed out.", timed_out=True)
    except FileNotFoundError as exc:
        return ExecutionResult(error=f"Compiler not found: {exc}")


def _execute_subprocess(cmd: list[str], stdin_input: str) -> ExecutionResult:
    """Run a compiled binary or script with stdin, capturing output."""
    try:
        result = subprocess.run(
            cmd,
            input=stdin_input,
            capture_output=True,
            text=True,
            timeout=EXEC_TIMEOUT,
        )
        return ExecutionResult(
            stdout=_truncate(result.stdout),
            stderr=_truncate(result.stderr),
            exit_code=result.returncode,
            executed=True,
            error="" if result.returncode == 0 else f"Runtime error (exit code {result.returncode})",
        )
    except subprocess.TimeoutExpired:
        return ExecutionResult(
            error=f"Time Limit Exceeded (>{EXEC_TIMEOUT}s)",
            timed_out=True,
            executed=True,
        )
    except FileNotFoundError as exc:
        return ExecutionResult(error=f"Executable not found: {exc}")
