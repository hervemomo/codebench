"""OpenAI chat-completion wrapper with retry, quota handling, and token accounting.

Ported from notebook section 0-E ("LLM infrastructure"). No module-level
mutable state: callers that want a usage log pass a list in via `usage_log`.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

logger = logging.getLogger(__name__)

_REASONING_CHAT_MODEL_PREFIXES = ("o1", "o3", "o4", "gpt-5")

_QUOTA_CODES = {"insufficient_quota", "quota_exceeded", "billing_not_active", "account_deactivated"}


class LLMClient(Protocol):
    """Minimal shape of the OpenAI SDK client that codeframe depends on.

    Both `openai.OpenAI` and `tests.fixtures.fake_openai.FakeOpenAI` satisfy this.
    """

    chat: Any
    embeddings: Any


class _TransientLLMError(Exception):
    """Marks an error as retryable; wraps the original exception."""

    def __init__(self, cause: BaseException):
        super().__init__(str(cause))
        self.cause = cause


def _uses_max_completion_tokens(model: str) -> bool:
    """Reasoning/newer Chat Completions models require max_completion_tokens."""
    return str(model or "").lower().strip().startswith(_REASONING_CHAT_MODEL_PREFIXES)


def _build_chat_completion_kwargs(*, model, messages, temperature, max_tokens) -> dict:
    kwargs: dict[str, Any] = {"model": model, "messages": messages}
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        token_param = "max_completion_tokens" if _uses_max_completion_tokens(model) else "max_tokens"
        kwargs[token_param] = max_tokens
    return kwargs


def _retry_with_alternate_chat_params(client: LLMClient, request_kwargs: dict, error: BaseException):
    """Retry one non-transient BadRequest caused by parameter-name incompatibility."""
    msg = str(error).lower()
    retry_kwargs = dict(request_kwargs)
    changed = False

    if "max_tokens" in msg and "max_completion_tokens" in msg:
        if "max_tokens" in retry_kwargs:
            retry_kwargs["max_completion_tokens"] = retry_kwargs.pop("max_tokens")
            changed = True
        elif "max_completion_tokens" in retry_kwargs:
            retry_kwargs["max_tokens"] = retry_kwargs.pop("max_completion_tokens")
            changed = True

    if "temperature" in msg and ("unsupported" in msg or "does not support" in msg):
        if "temperature" in retry_kwargs:
            retry_kwargs.pop("temperature", None)
            changed = True

    if not changed:
        raise error

    logger.warning("Retrying OpenAI call with compatibility-adjusted parameters.")
    return client.chat.completions.create(**retry_kwargs)


def _dispatch_chat_call(client: LLMClient, request_kwargs: dict):
    """One raw attempt. Raises RuntimeError for fatal errors, _TransientLLMError for retryable ones."""
    try:
        return client.chat.completions.create(**request_kwargs)
    except Exception as e:
        status = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
        body = getattr(e, "body", None) or {}
        code = (body.get("error", {}).get("code") if isinstance(body, dict) else None) or getattr(e, "code", None) or ""
        msg = str(e).lower()

        if code in _QUOTA_CODES or "insufficient_quota" in msg:
            raise RuntimeError(
                "OpenAI quota exhausted — account has no credits. "
                "Add credits at https://platform.openai.com/account/billing, then retry."
            ) from e

        if status == 401 or "invalid_api_key" in msg:
            raise RuntimeError("Invalid API key. Set OPENAI_API_KEY as an environment variable.") from e

        if status == 400:
            return _retry_with_alternate_chat_params(client, request_kwargs, e)

        retryable = status in (429, 500, 502, 503, 504) or any(
            kw in msg for kw in ("rate limit", "too many requests", "timeout", "temporarily")
        )
        if not retryable:
            raise
        raise _TransientLLMError(e) from e


def extract_usage(resp: Any, *, model: str, messages: Optional[list[dict]] = None) -> dict:
    """Return a token-usage row for one successful call. Never raises."""
    usage = getattr(resp, "usage", None)
    if usage is None:
        return {"timestamp": datetime.now(timezone.utc).isoformat(), "model": model, "usage_unavailable": True}

    details = getattr(usage, "prompt_tokens_details", None)
    cached_tokens = getattr(details, "cached_tokens", None) if details is not None else None
    prompt_chars = sum(len(str(m.get("content", ""))) for m in messages) if messages else None

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "prompt_tokens": getattr(usage, "prompt_tokens", None),
        "completion_tokens": getattr(usage, "completion_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "cached_prompt_tokens": cached_tokens,
        "prompt_chars_approx": prompt_chars,
    }


def chat_with_retry(
    client: LLMClient,
    *,
    model: str,
    messages: list[dict],
    temperature: Optional[float],
    max_tokens: Optional[int],
    timeout: float = 180.0,
    max_retries: int = 10,
    base_delay: float = 2.0,
    max_delay: float = 90.0,
    usage_log: Optional[list[dict]] = None,
):
    """Rate-limit-safe OpenAI chat wrapper with quota-aware fail-fast logic.

    Retried (transient): HTTP 429, 5xx, timeout.
    Not retried (fatal): insufficient_quota (billing), invalid_api_key.
    A one-time compatibility fallback handles unsupported max_tokens /
    max_completion_tokens / temperature parameter names (HTTP 400).

    On success, if `usage_log` is provided, a token-usage row is appended to it.
    """
    request_kwargs = _build_chat_completion_kwargs(
        model=model, messages=messages, temperature=temperature, max_tokens=max_tokens
    )
    request_kwargs["timeout"] = timeout

    retryer = Retrying(
        stop=stop_after_attempt(max(1, max_retries)),
        wait=wait_exponential_jitter(initial=base_delay, max=max_delay),
        retry=retry_if_exception_type(_TransientLLMError),
        reraise=True,
    )
    try:
        resp = retryer(_dispatch_chat_call, client, request_kwargs)
    except _TransientLLMError as e:
        raise e.cause from None

    if usage_log is not None:
        usage_log.append(extract_usage(resp, model=model, messages=messages))
    return resp


def strip_code_fence(text: str) -> str:
    """Remove a leading/trailing ```json ... ``` fence, if present."""
    text = re.sub(r"^```(?:json)?\n?", "", text.strip())
    text = re.sub(r"\n?```$", "", text)
    return text


def extract_json(raw: str) -> str:
    """Extract a JSON object/array from an LLM response.

    1. If fenced (```json ... ``` or ``` ... ```), return the fenced contents.
    2. Otherwise, scan forward from the first '{' or '[' with string- and
       escape-aware brace/bracket balancing to find the smallest complete value.
    3. Fall through to raw.strip() so json.loads() raises a clear error.
    """
    text = raw.strip()

    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1).strip()

    start = -1
    open_char = ""
    close_char = ""
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            open_char = ch
            close_char = "}" if ch == "{" else "]"
            break
    if start == -1:
        return text

    depth = 0
    in_string = False
    escape = False
    for j in range(start, len(text)):
        ch = text[j]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                return text[start : j + 1].strip()

    return text[start:].strip()
