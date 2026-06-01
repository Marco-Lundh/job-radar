import json

RATE_LIMIT_MSG = "Rate limit reached — please wait a moment and try again."


def _sse(event: dict[str, object]) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "rate_limit" in s
