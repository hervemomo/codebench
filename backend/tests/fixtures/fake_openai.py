"""Deterministic fake OpenAI client for tests and the --fake-llm demo.

Mimics the subset of `openai.OpenAI` that codeframe uses:
`.chat.completions.create(...)` and `.embeddings.create(...)`. No network
calls, no randomness that varies across processes (all "randomness" is
seeded from a stable hash of the input text, not Python's hash()).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Optional

# category -> (keywords, human label). Shared by embeddings, codebook
# generation, and coding so a fake "cluster" maps to a fake "code" that
# actually gets assigned to the responses that produced it.
THEME_KEYWORDS: dict[int, tuple[list[str], str]] = {
    0: (["taste", "flavor", "flavour", "delicious", "sweet"], "Taste & Flavor"),
    1: (["price", "afford", "value", "cheap", "cost", "money"], "Price & Value"),
    2: (["packaging", "bottle", "can", "design", "label"], "Packaging & Design"),
    3: (["available", "store", "shop", "stock", "find"], "Availability"),
    4: (["energy", "energetic", "boost", "energized", "healthier", "health"], "Energy & Health"),
}

NO_MATCH_MARKER = "###NO_MATCH###"


def stable_seed(text: str) -> int:
    """Deterministic, cross-process-stable seed (unlike Python's hash())."""
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest(), 16) % (2**32)


def category_for(text: str) -> int:
    t = f" {text.lower()} "
    for cat, (keywords, _label) in THEME_KEYWORDS.items():
        if any(f" {kw}" in t or t.startswith(kw) for kw in keywords):
            return cat
    return -1


def label_for_category(cat: int) -> Optional[str]:
    entry = THEME_KEYWORDS.get(cat)
    return entry[1] if entry else None


def label_for_block(block_text: str, fallback_index: int) -> str:
    block_lower = block_text.lower()
    counts = {cat: sum(block_lower.count(kw) for kw in keywords) for cat, (keywords, _label) in THEME_KEYWORDS.items()}
    best_cat = max(counts, key=counts.get) if counts else None
    if best_cat is not None and counts[best_cat] > 0:
        return THEME_KEYWORDS[best_cat][1]
    return f"Theme {fallback_index + 1}"


def embedding_for_text(text: str, dim: int = 16) -> list[float]:
    """Deterministic embedding: small per-text jitter plus a strong category-axis offset."""
    import random

    rng = random.Random(stable_seed(text))
    vec = [rng.uniform(-0.05, 0.05) for _ in range(dim)]
    cat = category_for(text)
    if cat >= 0:
        vec[cat % dim] += 3.0
    else:
        vec[rng.randrange(dim)] += 1.0
    return vec


# ── Fake response object shapes (mimic the OpenAI SDK) ──────────────────────


class _Message:
    def __init__(self, content: str):
        self.content = content


class _Choice:
    def __init__(self, content: str, finish_reason: str = "stop"):
        self.message = _Message(content)
        self.finish_reason = finish_reason


class _Usage:
    def __init__(self, prompt_tokens: int = 20, completion_tokens: int = 20, total_tokens: int = 40):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.prompt_tokens_details = None


class _ChatResponse:
    def __init__(self, content: str, finish_reason: str = "stop"):
        self.choices = [_Choice(content, finish_reason)]
        self.usage = _Usage()


class _EmbeddingItem:
    def __init__(self, embedding: list[float], index: int):
        self.embedding = embedding
        self.index = index


class _EmbeddingResponse:
    def __init__(self, data: list[_EmbeddingItem], total_tokens: int):
        self.data = data
        self.usage = _Usage(total_tokens=total_tokens)


# ── Prompt parsing helpers ───────────────────────────────────────────────────


def _extract_codebook_names(user_content: str) -> list[str]:
    match = re.search(r"CODEBOOK \(use ONLY these codes\):\n(.*?)\n\n", user_content, re.DOTALL)
    block = match.group(1) if match else ""
    names = []
    for line in block.splitlines():
        line = line.strip()
        m = re.match(r"^\d+\.\s+(.*)$", line)
        if not m:
            continue
        rest = m.group(1).strip().strip("*").strip()
        rest = rest.split(":", 1)[0].strip()
        rest = re.sub(r"^\[[^\]]*\]\s*", "", rest)
        if rest:
            names.append(rest)
    return names


INVALID_CODE_MARKER = "###INVALID_CODE###"


def _coding_result_for_text(text: str, codebook_names: list[str], *, with_reasoning: bool = False) -> dict:
    if not codebook_names or NO_MATCH_MARKER in text:
        result = {"codes": []}
        if with_reasoning:
            result["reasoning"] = "No codebook entry matched this response."
        return result

    if INVALID_CODE_MARKER in text:
        # Simulate the LLM hallucinating a code name that isn't in the codebook.
        return {"codes": [{"code": "Nonexistent Hallucinated Code", "confidence": 0.4}]}

    other_names = [n for n in codebook_names if "other" in n.lower() or "autre" in n.lower()]
    non_other = [n for n in codebook_names if n not in other_names] or codebook_names

    cat = category_for(text)
    label = label_for_category(cat) if cat >= 0 else None
    chosen = next((n for n in non_other if label and label.lower() in n.lower()), None)
    if chosen is None:
        chosen = non_other[stable_seed(text) % len(non_other)]

    result = {"codes": [{"code": chosen, "confidence": 0.9}]}
    if with_reasoning:
        result["reasoning"] = f'Matched theme "{chosen}".'
    return result


# ── Canned-response handlers, one per prompt "shape" codeframe sends ────────


class _Completions:
    def create(
        self, *, model: str, messages: list[dict], temperature: Optional[float] = None,
        max_tokens: Optional[int] = None, max_completion_tokens: Optional[int] = None,
        timeout: Optional[float] = None, **_kwargs: Any,
    ) -> _ChatResponse:
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user = next((m["content"] for m in messages if m.get("role") == "user"), "")
        budget = max_tokens if max_tokens is not None else max_completion_tokens

        if system == "Qualitative research expert. Return ONLY complete valid JSON.":
            return self._codebook_response(user, budget)
        if system == "Qualitative research expert. Return ONLY valid JSON.":
            return self._enrichment_response(user)
        if system == "Qualitative coding expert. Return ONLY valid JSON.":
            if "Propose exactly" in user:
                return self._split_proposal_response(user)
            return self._merge_proposal_response(user)
        if system.startswith("Translate to"):
            return self._translation_response(user)
        if system == "Return only valid JSON.":
            return self._coding_batch_response(user)
        if system == "Survey coder. Return ONLY raw JSON.":
            return self._coding_single_response(user)

        raise ValueError(f"FakeOpenAI: no canned response for system message: {system!r}")

    @staticmethod
    def _codebook_response(user_content: str, budget: Optional[int]) -> _ChatResponse:
        n_match = re.search(r"Create exactly (\d+) distinct codes", user_content)

        # Bound the search to the GROUPS section first (single non-nested lazy
        # quantifier - safe), then split on cluster markers with a plain,
        # non-nested regex. Avoid nested-quantifier patterns like
        # `(?:.+\n?)*?` here: on a multi-KB prompt they cause catastrophic
        # backtracking and can hang for effectively forever.
        groups_match = re.search(r"GROUPS:\n(.*?)\n\nINSTRUCTIONS:", user_content, re.DOTALL)
        groups_text = groups_match.group(1) if groups_match else user_content
        blocks = [b for b in re.split(r"\n### Cluster \d+\n?", groups_text)[1:]]
        n_codes = int(n_match.group(1)) if n_match else max(1, len(blocks))

        if budget is not None and budget < 120 * n_codes:
            return _ChatResponse(content='{"codes": [', finish_reason="length")

        names: list[str] = []
        seen: set[str] = set()
        for i in range(n_codes):
            block = blocks[i] if i < len(blocks) else ""
            label = label_for_block(block, i)
            candidate = label
            suffix = 2
            while candidate in seen:
                candidate = f"{label} {suffix}"
                suffix += 1
            seen.add(candidate)
            names.append(candidate)

        codes = [
            {
                "name": name,
                "definition": f"Responses about {name.lower()}.",
                "inclusion_criteria": [f"Mentions {name.lower()}."],
                "exclusion_criteria": ["Off-topic response."],
                "example_verbatims": ["Example verbatim."],
            }
            for name in names
        ]
        return _ChatResponse(content=json.dumps({"codes": codes}))

    @staticmethod
    def _enrichment_response(user_content: str) -> _ChatResponse:
        pattern = re.compile(r'- name=("(?:[^"\\]|\\.)*")(?: \| code_id=("(?:[^"\\]|\\.)*"))?')
        codes = []
        for m in pattern.finditer(user_content):
            name = json.loads(m.group(1))
            code_id = json.loads(m.group(2)) if m.group(2) else None
            entry = {
                "name": name,
                "definition": f"Definition for {name}.",
                "inclusion_criteria": [f"Matches the theme of {name}."],
                "exclusion_criteria": ["Does not match this theme."],
                "example_verbatims": ["Example verbatim 1.", "Example verbatim 2."],
            }
            if code_id:
                entry["code_id"] = code_id
            codes.append(entry)
        return _ChatResponse(content=json.dumps({"codes": codes}))

    @staticmethod
    def _split_proposal_response(user_content: str) -> _ChatResponse:
        if "AI_SPLIT_PARSE_FAIL" in user_content:
            return _ChatResponse(content="not valid json at all")
        if "AI_SPLIT_EMPTY" in user_content:
            return _ChatResponse(content=json.dumps({"subcodes": []}))

        n_match = re.search(r"Propose exactly (\d+) distinct", user_content)
        n = int(n_match.group(1)) if n_match else 2
        parent_match = re.search(r'The code "([^"]*)" is too broad', user_content)
        parent = parent_match.group(1) if parent_match else "Parent"
        subcodes = [f"{parent} - sub {i + 1}" for i in range(n)]
        return _ChatResponse(content=json.dumps({"subcodes": subcodes}))

    @staticmethod
    def _merge_proposal_response(user_content: str) -> _ChatResponse:
        if "AI_MERGE_NO_NAME" in user_content:
            return _ChatResponse(content=json.dumps({"name": "", "definition": ""}))

        refs = [r.strip() for r in re.findall(r"\*\*(.+?)\*\*", user_content)]
        label = " + ".join(refs) if refs else "Merged"
        name = f"Merged: {label}"[:60]
        return _ChatResponse(content=json.dumps({"name": name, "definition": f"Consolidated theme combining: {label}."}))

    @staticmethod
    def _translation_response(user_content: str) -> _ChatResponse:
        items = re.findall(r"^\[(\d+)\] (.*)$", user_content, re.MULTILINE)
        items.sort(key=lambda x: int(x[0]))
        texts = [t for _, t in items]

        # Always wrong-length, even for a single-item retry -> exercises the
        # "per-item retry also fails, keep original text" path.
        if any("ALWAYS_TRANSLATE_FAIL" in t for t in texts):
            return _ChatResponse(content=json.dumps([]))
        # Wrong-length only for multi-item batches -> exercises the
        # "batch fails, retry one-by-one, retry succeeds" path.
        if len(texts) > 1 and any("BATCH_TRANSLATE_FAIL" in t for t in texts):
            return _ChatResponse(content=json.dumps(["mismatched length"]))

        translated = [f"[TR] {t}" for t in texts]
        return _ChatResponse(content=json.dumps(translated))

    @staticmethod
    def _coding_batch_response(user_content: str) -> _ChatResponse:
        names = _extract_codebook_names(user_content)
        wants_reasoning = '"reasoning"' in user_content
        items = re.findall(r'\[(\d+)\] "(.*?)"\n', user_content)
        items.sort(key=lambda x: int(x[0]))
        texts = [t for _, t in items]

        # Force the whole batch response to be unparseable so codeframe falls
        # back to single-item coding for every response in this batch.
        if any("BATCH_CODE_FAIL" in t for t in texts):
            return _ChatResponse(content="not valid json for this batch")

        array = [
            {"response_num": i + 1, **_coding_result_for_text(text, names, with_reasoning=wants_reasoning)}
            for i, text in enumerate(texts)
        ]
        return _ChatResponse(content=json.dumps(array))

    @staticmethod
    def _coding_single_response(user_content: str) -> _ChatResponse:
        names = _extract_codebook_names(user_content)
        wants_reasoning = '"reasoning"' in user_content
        m = re.search(r"RESPONSE: (.*)\n", user_content)
        text = m.group(1) if m else ""
        return _ChatResponse(content=json.dumps(_coding_result_for_text(text, names, with_reasoning=wants_reasoning)))


class _Chat:
    def __init__(self) -> None:
        self.completions = _Completions()


class _Embeddings:
    def create(self, *, model: str, input: list[str], timeout: Optional[float] = None) -> _EmbeddingResponse:
        data = [_EmbeddingItem(embedding_for_text(t), i) for i, t in enumerate(input)]
        total_tokens = sum(max(1, len(t.split())) for t in input)
        return _EmbeddingResponse(data, total_tokens=total_tokens)


class FakeOpenAI:
    """Deterministic drop-in for `openai.OpenAI` used by codeframe's tests and demo."""

    def __init__(self) -> None:
        self.chat = _Chat()
        self.embeddings = _Embeddings()
