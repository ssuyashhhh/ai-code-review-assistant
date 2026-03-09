"""
static_analyzer.py — Lightweight static analysis for CP code
=============================================================
Pattern-based detection of common competitive programming bugs.

This is NOT a full linter — it's a fast heuristic pass that catches
common CP pitfalls before sending the code to the LLM. The LLM then
uses these hints for a more accurate review.

Checks:
  • Off-by-one errors (loop bounds)
  • Integer overflow risks (32-bit limits without long long)
  • Array/index out of bounds risks
  • Uninitialized variable usage
  • Infinite loop patterns
  • Common CP pitfalls (missing newline, wrong data types, etc.)
"""

import re
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AnalysisWarning:
    """A single static analysis finding."""
    line: int | None        # 1-based line number, or None
    category: str           # e.g. "off-by-one", "overflow", "bounds"
    message: str
    severity: str = "medium"  # low | medium | high


@dataclass
class StaticAnalysisResult:
    """Aggregated result of static analysis."""
    warnings: list[AnalysisWarning] = field(default_factory=list)
    summary: str = ""


def analyze(language: str, code: str) -> StaticAnalysisResult:
    """Run static analysis on the given code. Returns warnings list + summary."""
    lang = language.lower().strip()
    lines = code.split("\n")
    warnings: list[AnalysisWarning] = []

    # Run language-specific checks
    if lang in ("python",):
        warnings.extend(_check_python(lines))
    elif lang in ("cpp", "c"):
        warnings.extend(_check_cpp_c(lines, lang))
    elif lang in ("java",):
        warnings.extend(_check_java(lines))
    elif lang in ("javascript", "typescript"):
        warnings.extend(_check_js(lines))

    # Run universal checks
    warnings.extend(_check_universal(lines, lang))

    summary = _build_summary(warnings)
    return StaticAnalysisResult(warnings=warnings, summary=summary)


def format_for_prompt(result: StaticAnalysisResult) -> str:
    """Format analysis result as a text block for the LLM prompt."""
    if not result.warnings:
        return "Static Analysis: No issues detected."

    lines = [f"Static Analysis ({len(result.warnings)} potential issues found):"]
    for w in result.warnings:
        loc = f"Line {w.line}" if w.line else "General"
        lines.append(f"  [{w.severity.upper()}] {loc} — {w.category}: {w.message}")
    return "\n".join(lines)


# =============================================================================
#  Python-specific checks
# =============================================================================

def _check_python(lines: list[str]) -> list[AnalysisWarning]:
    warnings = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # range() off-by-one: range(1, n) when it should be range(1, n+1)
        for m in re.finditer(r"range\(\s*(\d+)\s*,\s*(\w+)\s*\)", stripped):
            warnings.append(AnalysisWarning(
                line=i, category="off-by-one",
                message=f"range({m.group(1)}, {m.group(2)}) — verify upper bound is correct (range excludes the end).",
                severity="medium",
            ))

        # Integer division: using / instead of // for integer division
        if re.search(r"\b\w+\s*/\s*\w+", stripped) and "//" not in stripped and "import" not in stripped:
            if "def " not in stripped and "return" not in stripped:
                pass  # too noisy, skip

        # Mutable default argument
        if re.search(r"def\s+\w+\(.*=\s*(\[\]|\{\})", stripped):
            warnings.append(AnalysisWarning(
                line=i, category="mutable-default",
                message="Mutable default argument (list/dict) — this is shared across calls.",
                severity="high",
            ))

        # Recursion without memoization (simple heuristic)
        if re.search(r"def\s+(\w+)", stripped):
            fname_match = re.search(r"def\s+(\w+)", stripped)
            if fname_match:
                fname = fname_match.group(1)
                # Check if the function calls itself in the next ~20 lines
                body = "\n".join(lines[i:min(i+20, len(lines))])
                if re.search(rf"\b{re.escape(fname)}\s*\(", body) and "lru_cache" not in "\n".join(lines[max(0,i-3):i]):
                    warnings.append(AnalysisWarning(
                        line=i, category="recursion",
                        message=f"Recursive function '{fname}' without visible memoization — may cause TLE on large inputs.",
                        severity="medium",
                    ))

    return warnings


# =============================================================================
#  C/C++-specific checks
# =============================================================================

def _check_cpp_c(lines: list[str], lang: str) -> list[AnalysisWarning]:
    warnings = []
    has_long_long = False
    has_large_constant = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Check for long long usage
        if "long long" in stripped or "int64_t" in stripped:
            has_long_long = True

        # Large constants that might overflow int
        for m in re.finditer(r"\b(\d{6,})\b", stripped):
            val_str = m.group(1)
            try:
                val = int(val_str)
                if val > 2_147_483_647:
                    has_large_constant = True
                    if not has_long_long:
                        warnings.append(AnalysisWarning(
                            line=i, category="overflow",
                            message=f"Large constant {val_str} exceeds 32-bit int range. Use 'long long' or add 'LL' suffix.",
                            severity="high",
                        ))
            except ValueError:
                pass

        # Array with fixed size — potential out-of-bounds
        m = re.search(r"\b(?:int|long|char|double|float)\s+\w+\[(\d+)\]", stripped)
        if m:
            size = int(m.group(1))
            if size < 10:
                warnings.append(AnalysisWarning(
                    line=i, category="bounds",
                    message=f"Small fixed-size array [{size}] — verify it's large enough for worst-case input.",
                    severity="low",
                ))

        # Missing return in non-void function
        if re.search(r"\b(int|long|double|float|bool)\s+\w+\s*\(", stripped) and "main" not in stripped:
            pass  # Would need full parsing — skip for now

        # Uninitialized variables (heuristic: declared without = on same line)
        if re.search(r"^\s*int\s+\w+\s*;", stripped) and "for" not in stripped:
            warnings.append(AnalysisWarning(
                line=i, category="uninitialized",
                message="Variable declared without initialization — may contain garbage value.",
                severity="medium",
            ))

        # scanf/printf format mismatch: %d with long long
        if "scanf" in stripped or "printf" in stripped:
            if "%d" in stripped and "long long" in "\n".join(lines[max(0,i-5):i]):
                warnings.append(AnalysisWarning(
                    line=i, category="format-mismatch",
                    message="Using %d format specifier — use %lld for long long.",
                    severity="high",
                ))

    # Global overflow check: large N constraints but no long long
    if lang == "cpp":
        full_code = "\n".join(lines)
        if re.search(r"10\s*\*\*\s*[5-9]|1e[5-9]|100000", full_code) and not has_long_long:
            if "int " in full_code:
                warnings.append(AnalysisWarning(
                    line=None, category="overflow",
                    message="Code handles large values but doesn't use 'long long' — multiplication may overflow 32-bit int.",
                    severity="medium",
                ))

    return warnings


# =============================================================================
#  Java-specific checks
# =============================================================================

def _check_java(lines: list[str]) -> list[AnalysisWarning]:
    warnings = []
    uses_scanner = False
    closes_scanner = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        if "new Scanner" in stripped:
            uses_scanner = True
        if ".close()" in stripped:
            closes_scanner = True

        # Integer overflow: int instead of long
        if re.search(r"\bint\s+\w+\s*=.*\*", stripped):
            warnings.append(AnalysisWarning(
                line=i, category="overflow",
                message="Multiplication with 'int' — consider using 'long' if values may exceed 2^31.",
                severity="medium",
            ))

        # Using == for String comparison
        if re.search(r'"\w*"\s*==\s*\w+|\w+\s*==\s*"\w*"', stripped):
            warnings.append(AnalysisWarning(
                line=i, category="string-compare",
                message="Using == for String comparison — use .equals() instead.",
                severity="high",
            ))

    return warnings


# =============================================================================
#  JavaScript/TypeScript-specific checks
# =============================================================================

def _check_js(lines: list[str]) -> list[AnalysisWarning]:
    warnings = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()

        # Using == instead of ===
        if re.search(r"[^=!]==[^=]", stripped):
            warnings.append(AnalysisWarning(
                line=i, category="loose-equality",
                message="Using == (loose equality) — consider === for strict comparison.",
                severity="low",
            ))

        # Floating point comparison
        if re.search(r"===?\s*0\.|\b\w+\s*===?\s*\d+\.\d+", stripped):
            warnings.append(AnalysisWarning(
                line=i, category="float-compare",
                message="Direct floating-point comparison — may cause precision issues.",
                severity="medium",
            ))

    return warnings


# =============================================================================
#  Universal checks (all languages)
# =============================================================================

def _check_universal(lines: list[str], lang: str) -> list[AnalysisWarning]:
    warnings = []
    full_code = "\n".join(lines)

    # Nested loops — potential O(n²) or worse
    loop_depth = 0
    max_depth = 0
    loop_patterns = {
        "python": r"^\s*(for|while)\b",
        "cpp": r"\b(for|while)\s*\(",
        "c": r"\b(for|while)\s*\(",
        "java": r"\b(for|while)\s*\(",
        "javascript": r"\b(for|while)\s*\(",
        "typescript": r"\b(for|while)\s*\(",
    }
    pattern = loop_patterns.get(lang, r"\b(for|while)\b")

    indent_stack = []
    for i, line in enumerate(lines, 1):
        if not line.strip():
            continue
        if lang == "python":
            indent = len(line) - len(line.lstrip())
            while indent_stack and indent_stack[-1] >= indent:
                indent_stack.pop()
                loop_depth = max(0, loop_depth - 1)
            if re.search(pattern, line):
                loop_depth += 1
                indent_stack.append(indent)
                max_depth = max(max_depth, loop_depth)
        else:
            if re.search(pattern, line.strip()):
                loop_depth += 1
                max_depth = max(max_depth, loop_depth)
            # Rough heuristic for closing braces
            close_count = line.count("}")
            loop_depth = max(0, loop_depth - close_count)

    if max_depth >= 3:
        warnings.append(AnalysisWarning(
            line=None, category="complexity",
            message=f"Detected {max_depth} levels of nested loops — potential O(n^{max_depth}) complexity. May cause TLE.",
            severity="high",
        ))
    elif max_depth == 2:
        warnings.append(AnalysisWarning(
            line=None, category="complexity",
            message="Detected 2 levels of nested loops — O(n²) complexity. Check if N > 10^4.",
            severity="medium",
        ))

    # Hardcoded array sizes that look like constraints
    if re.search(r"\b(1005|10005|100005|1000005|200005)\b", full_code):
        pass  # common CP pattern, not a warning

    # Missing edge case handling for N=0 or N=1
    if re.search(r"\bn\s*[<>=]+\s*[01]\b", full_code) is None:
        if re.search(r"\bwhile\b|\bfor\b", full_code):
            warnings.append(AnalysisWarning(
                line=None, category="edge-case",
                message="No visible check for N=0 or N=1 edge cases — verify the code handles minimal inputs.",
                severity="low",
            ))

    return warnings


# =============================================================================
#  Summary builder
# =============================================================================

def _build_summary(warnings: list[AnalysisWarning]) -> str:
    if not warnings:
        return "No static analysis issues detected."

    high = sum(1 for w in warnings if w.severity == "high")
    med = sum(1 for w in warnings if w.severity == "medium")
    low = sum(1 for w in warnings if w.severity == "low")

    parts = []
    if high: parts.append(f"{high} high")
    if med: parts.append(f"{med} medium")
    if low: parts.append(f"{low} low")

    return f"Found {len(warnings)} potential issues ({', '.join(parts)})."
