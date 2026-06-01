import json

from agents._utils import RATE_LIMIT_MSG, _is_rate_limit, _sse


def test_sse_has_correct_format():
    result = _sse({"type": "progress", "message": "hello"})
    assert result.startswith("data: ")
    assert result.endswith("\n\n")


def test_sse_payload_is_valid_json():
    result = _sse({"type": "done"})
    payload = json.loads(result.removeprefix("data: ").removesuffix("\n\n"))
    assert payload == {"type": "done"}


def test_sse_preserves_non_ascii():
    result = _sse({"message": "åäö"})
    assert "åäö" in result


def test_is_rate_limit_with_429():
    assert _is_rate_limit(Exception("HTTP 429 Too Many Requests"))


def test_is_rate_limit_with_rate_limit_text():
    assert _is_rate_limit(Exception("rate limit exceeded"))


def test_is_rate_limit_with_underscore_variant():
    assert _is_rate_limit(Exception("rate_limit_error"))


def test_is_rate_limit_false_for_generic_error():
    assert not _is_rate_limit(Exception("Internal server error"))


def test_is_rate_limit_false_for_value_error():
    assert not _is_rate_limit(ValueError("something went wrong"))


def test_rate_limit_msg_is_non_empty():
    assert len(RATE_LIMIT_MSG) > 0
