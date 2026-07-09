import json
from types import SimpleNamespace

import pytest

from codeframe.llm import chat_with_retry, extract_json, extract_usage, strip_code_fence


class _FakeResponse:
    def __init__(self, content="ok"):
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content), finish_reason="stop")]
        self.usage = SimpleNamespace(prompt_tokens=3, completion_tokens=5, total_tokens=8, prompt_tokens_details=None)


class _FlakyCompletions:
    def __init__(self, fail_times, status_code=429):
        self.calls = 0
        self.fail_times = fail_times
        self.status_code = status_code

    def create(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            err = Exception("rate limit exceeded, please retry")
            err.status_code = self.status_code
            raise err
        return _FakeResponse()


class _StubClient:
    def __init__(self, completions):
        self.chat = SimpleNamespace(completions=completions)


def test_chat_with_retry_retries_transient_errors_then_succeeds():
    completions = _FlakyCompletions(fail_times=2)
    client = _StubClient(completions)

    resp = chat_with_retry(
        client, model="gpt-4.1-mini", messages=[{"role": "user", "content": "hi"}],
        temperature=0.1, max_tokens=10, max_retries=5, base_delay=0.01, max_delay=0.02,
    )

    assert resp.choices[0].message.content == "ok"
    assert completions.calls == 3


def test_chat_with_retry_gives_up_after_max_retries():
    completions = _FlakyCompletions(fail_times=10)
    client = _StubClient(completions)

    with pytest.raises(Exception):
        chat_with_retry(
            client, model="gpt-4.1-mini", messages=[{"role": "user", "content": "hi"}],
            temperature=0.1, max_tokens=10, max_retries=3, base_delay=0.01, max_delay=0.02,
        )
    assert completions.calls == 3


def test_chat_with_retry_quota_error_is_not_retried():
    class _QuotaCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            err = Exception("insufficient_quota")
            err.status_code = 429
            err.body = {"error": {"code": "insufficient_quota"}}
            raise err

    completions = _QuotaCompletions()
    client = _StubClient(completions)

    with pytest.raises(RuntimeError):
        chat_with_retry(
            client, model="m", messages=[{"role": "user", "content": "x"}],
            temperature=0.1, max_tokens=10, max_retries=5, base_delay=0.01, max_delay=0.02,
        )
    assert completions.calls == 1


def test_chat_with_retry_invalid_api_key_is_not_retried():
    class _AuthCompletions:
        def __init__(self):
            self.calls = 0

        def create(self, **kwargs):
            self.calls += 1
            err = Exception("invalid_api_key provided")
            err.status_code = 401
            raise err

    completions = _AuthCompletions()
    client = _StubClient(completions)

    with pytest.raises(RuntimeError):
        chat_with_retry(
            client, model="m", messages=[{"role": "user", "content": "x"}],
            temperature=0.1, max_tokens=10, max_retries=5, base_delay=0.01, max_delay=0.02,
        )
    assert completions.calls == 1


def test_chat_with_retry_bad_request_swaps_max_tokens_param_name():
    class _Client:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                err = Exception("Unsupported: 'max_tokens' is not supported with this model, use 'max_completion_tokens' instead")
                err.status_code = 400
                raise err
            return _FakeResponse()

    completions = _Client()
    client = _StubClient(completions)

    # gpt-4.1-mini is a non-reasoning model, so the first attempt uses max_tokens.
    resp = chat_with_retry(client, model="gpt-4.1-mini", messages=[{"role": "user", "content": "hi"}], temperature=0.1, max_tokens=50)

    assert resp.choices[0].message.content == "ok"
    assert len(completions.calls) == 2
    assert "max_tokens" not in completions.calls[1]
    assert completions.calls[1]["max_completion_tokens"] == 50


def test_chat_with_retry_bad_request_drops_unsupported_temperature():
    class _Client:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                err = Exception("temperature is unsupported for this model")
                err.status_code = 400
                raise err
            return _FakeResponse()

    completions = _Client()
    client = _StubClient(completions)

    resp = chat_with_retry(client, model="gpt-4.1-mini", messages=[{"role": "user", "content": "hi"}], temperature=0.9, max_tokens=50)

    assert resp.choices[0].message.content == "ok"
    assert "temperature" not in completions.calls[1]


def test_chat_with_retry_bad_request_unrecognized_reason_reraises():
    class _Client:
        def create(self, **kwargs):
            err = Exception("some unrelated 400 error")
            err.status_code = 400
            raise err

    client = _StubClient(_Client())

    with pytest.raises(Exception, match="unrelated 400 error"):
        chat_with_retry(client, model="gpt-4.1-mini", messages=[{"role": "user", "content": "hi"}], temperature=0.1, max_tokens=50)


def test_chat_with_retry_appends_usage_log():
    completions = _FlakyCompletions(fail_times=0)
    client = _StubClient(completions)
    usage_log = []

    chat_with_retry(
        client, model="gpt-4.1-mini", messages=[{"role": "user", "content": "hi"}],
        temperature=0.1, max_tokens=10, usage_log=usage_log,
    )

    assert len(usage_log) == 1
    assert usage_log[0]["total_tokens"] == 8


def test_extract_usage_handles_missing_usage_gracefully():
    resp = SimpleNamespace(usage=None)
    row = extract_usage(resp, model="m")
    assert row["usage_unavailable"] is True


def test_extract_json_handles_fenced_block():
    raw = '```json\n{"a": 1}\n```'
    assert json.loads(extract_json(raw)) == {"a": 1}


def test_extract_json_scans_for_balanced_braces_in_prose():
    raw = 'Sure, here it is: {"a": 1, "b": [1, 2, 3]} -- hope that helps!'
    assert json.loads(extract_json(raw)) == {"a": 1, "b": [1, 2, 3]}


def test_extract_json_handles_array():
    raw = 'noise before ["one", "two"] noise after'
    assert json.loads(extract_json(raw)) == ["one", "two"]


def test_strip_code_fence():
    assert strip_code_fence('```json\n[1,2]\n```') == "[1,2]"
    assert strip_code_fence("[1,2]") == "[1,2]"


def test_extract_json_no_json_like_content_returns_raw_text():
    assert extract_json("just plain text, nothing here") == "just plain text, nothing here"


def test_extract_json_handles_escaped_quotes_inside_strings():
    raw = 'prefix {"a": "she said \\"hi\\" to me"} suffix'
    parsed = json.loads(extract_json(raw))
    assert parsed["a"] == 'she said "hi" to me'


def test_extract_json_unbalanced_braces_returns_partial_tail():
    raw = 'noise {"a": 1, "b": [1, 2'
    result = extract_json(raw)
    assert result.startswith('{"a": 1')
