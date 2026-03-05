"""
utils/response_normaliser.py
AI Data Assistant — POC2

Post-processes raw agent output before it reaches the caller.
Strips markdown fences, <think> tags, excessive whitespace,
and enforces a clean, consistent response format.

This is the component that prevents "code spill" to the user —
raw model internals never reach the response layer.

Usage:
    from utils.response_normaliser import normalise

    clean = normalise(raw_agent_output)
"""

import re
from loguru import logger


# ── Patterns to strip ────────────────────────────────────────────────────────

# Qwen3 and other models sometimes emit <think>...</think> blocks
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)

# Markdown code fences: ```sql ... ``` or ``` ... ```
_CODE_FENCE = re.compile(r"```[a-zA-Z]*\n?(.*?)```", re.DOTALL)

# Trailing whitespace on every line
_TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)

# More than 2 consecutive blank lines → normalise to 1
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")

# Common model preamble phrases that add no value
_PREAMBLE_PHRASES = re.compile(
    r"^(Sure[,!.]?\s*|Certainly[,!.]?\s*|Of course[,!.]?\s*|"
    r"Absolutely[,!.]?\s*|Great[,!.]?\s*|I'll help you with that[.!]?\s*|"
    r"I can help with that[.!]?\s*)",
    re.IGNORECASE,
)


def normalise(text: str) -> str:
    """
    Clean raw agent/model output and return a normalised string safe
    for delivery to the caller.

    Steps applied in order:
    1. Strip <think>...</think> blocks
    2. Unwrap markdown code fences (keep content, remove fences)
    3. Strip common preamble phrases
    4. Normalise whitespace
    5. Strip leading/trailing blank lines

    Returns the cleaned string. If the result is empty after cleaning,
    returns a safe fallback message.
    """
    if not text or not text.strip():
        return _safe_fallback("empty input")

    original_length = len(text)

    # 1. Remove <think> blocks
    text = _THINK_BLOCK.sub("", text)

    # 2. Unwrap code fences — keep the content inside
    text = _CODE_FENCE.sub(lambda m: m.group(1).strip(), text)

    # 3. Strip preamble
    text = _PREAMBLE_PHRASES.sub("", text).strip()

    # 4. Normalise whitespace
    text = _TRAILING_WHITESPACE.sub("", text)
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    text = text.strip()

    if not text:
        return _safe_fallback("all content stripped")

    if len(text) < original_length * 0.1:
        # More than 90% was stripped — suspicious, log it
        logger.warning(
            f"Response normaliser removed >90% of content "
            f"({original_length} → {len(text)} chars). Check model output."
        )

    return text


def normalise_sql(sql: str) -> str:
    """
    Normalise a SQL string specifically:
    - Strip fences and think blocks
    - Uppercase SQL keywords for readability
    - Collapse excess whitespace within the SQL
    """
    sql = normalise(sql)

    # Basic keyword uppercasing for the most common keywords
    keywords = [
        "select", "from", "where", "join", "inner join", "left join",
        "right join", "group by", "order by", "having", "limit", "top",
        "distinct", "count", "sum", "avg", "min", "max", "as", "on",
        "and", "or", "not", "in", "like", "between", "is null",
        "is not null", "case", "when", "then", "else", "end",
    ]
    for kw in keywords:
        sql = re.sub(rf"\b{kw}\b", kw.upper(), sql, flags=re.IGNORECASE)

    # Collapse multiple spaces (but not newlines)
    sql = re.sub(r" {2,}", " ", sql)
    return sql.strip()


def _safe_fallback(reason: str) -> str:
    logger.warning(f"Response normaliser returning fallback ({reason})")
    return (
        "I was unable to generate a clear response to your request. "
        "Please try rephrasing your question, or contact the system administrator."
    )
