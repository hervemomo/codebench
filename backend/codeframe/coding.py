"""Apply a codebook to a dataframe of responses via batched LLM calls.

Ported from notebook section 2-B (response coding half).
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Callable, Optional

import numpy as np
import pandas as pd

from codeframe.codebook import Codebook, get_default_other_code_name, get_other_code_name, to_compact_prompt, to_full_prompt
from codeframe.config import CodingConfig, ProjectConfig
from codeframe.llm import LLMClient, chat_with_retry

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], None]


def _safe_confidence(value, default: float = 0.0) -> float:
    """Return a numeric confidence in [0.0, 1.0]; never raises."""
    try:
        if value is None or value == "":
            value = default
        value = float(value)
    except (TypeError, ValueError):
        value = float(default)
    if not np.isfinite(value):
        value = float(default)
    return max(0.0, min(1.0, value))


def _deduplicate_texts(texts: list[str]) -> tuple[list[str], list[int]]:
    """Return (unique_texts, index_map): index_map[i] -> position of texts[i] in unique_texts."""
    seen: dict[str, int] = {}
    unique: list[str] = []
    idx_map: list[int] = []
    for t in texts:
        if t not in seen:
            seen[t] = len(unique)
            unique.append(t)
        idx_map.append(seen[t])
    return unique, idx_map


def _coding_codebook_text(codebook: Codebook, coding_cfg: CodingConfig) -> str:
    return to_compact_prompt(codebook) if coding_cfg.use_compact_codebook_for_coding else to_full_prompt(codebook)


def _coding_instruction(codebook: Codebook, other_code: Optional[str]) -> str:
    base = "Assign ALL applicable codes." if codebook.multi_label else "Assign EXACTLY ONE code."
    if other_code:
        return f'{base} If no specific code applies, assign "{other_code}". Use ONLY code names exactly as written in the codebook.'
    return f"{base} Use ONLY code names exactly as written in the codebook."


def _code_single(client: LLMClient, text: str, codebook: Codebook, project_cfg: ProjectConfig, coding_cfg: CodingConfig, usage_log: Optional[list[dict]]) -> dict:
    """Code one response. Used as a fallback when a batch response cannot be parsed."""
    other_code = get_other_code_name(codebook, get_default_other_code_name(project_cfg))
    schema = ('{"codes":[{"code":"<name>","confidence":0.0}],"reasoning":"brief"}' if coding_cfg.save_coding_reasoning
              else '{"codes":[{"code":"<name>","confidence":0.0}]}')
    prompt = (
        "Assign codes to this survey response.\n\n"
        f"CODEBOOK (use ONLY these codes):\n{_coding_codebook_text(codebook, coding_cfg)}\n\n"
        f"RESPONSE: {text}\n\n"
        f"INSTRUCTIONS: {_coding_instruction(codebook, other_code)}\n"
        f"Include confidence 0.0-1.0. Return ONLY raw JSON:\n{schema}"
    )
    resp = chat_with_retry(
        client, model=project_cfg.coding_model,
        messages=[{"role": "system", "content": "Survey coder. Return ONLY raw JSON."}, {"role": "user", "content": prompt}],
        temperature=0.2, max_tokens=(450 if coding_cfg.save_coding_reasoning else 250),
        timeout=project_cfg.openai_timeout_seconds, max_retries=project_cfg.openai_max_retries, usage_log=usage_log,
    )
    content = re.sub(r"^```(?:json)?\n?", "", resp.choices[0].message.content.strip())
    content = re.sub(r"\n?```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"codes": []}


def _code_batch(
    client: LLMClient, texts: list[str], codebook: Codebook, project_cfg: ProjectConfig, coding_cfg: CodingConfig,
    *, progress_cb: Optional[ProgressCallback] = None, usage_log: Optional[list[dict]] = None,
) -> list[dict]:
    """Code a list of texts in batches, with pre-coding dedup and single-item fallback on parse failure."""
    unique_texts, idx_map = _deduplicate_texts(texts)
    unique_results: list[dict] = []
    other_code = get_other_code_name(codebook, get_default_other_code_name(project_cfg))
    instruction = _coding_instruction(codebook, other_code)
    schema = ('[{"response_num":1,"codes":[{"code":"<name>","confidence":0.0}],"reasoning":"brief"}]' if coding_cfg.save_coding_reasoning
              else '[{"response_num":1,"codes":[{"code":"<name>","confidence":0.0}]}]')

    batch_size = coding_cfg.coding_batch_size
    n_batches = max(1, math.ceil(len(unique_texts) / batch_size)) if unique_texts else 0

    for batch_i, i in enumerate(range(0, len(unique_texts), batch_size), start=1):
        batch = unique_texts[i : i + batch_size]
        numbered = "".join(f'\n[{j}] "{t}"\n' for j, t in enumerate(batch, 1))
        per_response_budget = 160 if coding_cfg.save_coding_reasoning else 90
        out_tokens = min(3500, max(400, len(batch) * per_response_budget))
        prompt = (
            "You are a precise qualitative survey coder.\n\n"
            f"CODEBOOK (use ONLY these codes):\n{_coding_codebook_text(codebook, coding_cfg)}\n\n"
            f"RESPONSES:\n{numbered}\n\n"
            f"INSTRUCTIONS: {instruction}\n"
            f"Include confidence 0.0-1.0.\nReturn a JSON array -- one object per response, in the same order:\n{schema}"
        )
        resp = chat_with_retry(
            client, model=project_cfg.coding_model,
            messages=[{"role": "system", "content": "Return only valid JSON."}, {"role": "user", "content": prompt}],
            temperature=0.1, max_tokens=out_tokens,
            timeout=project_cfg.openai_timeout_seconds, max_retries=project_cfg.openai_max_retries, usage_log=usage_log,
        )
        content = re.sub(r"^```(?:json)?\n?", "", resp.choices[0].message.content.strip())
        content = re.sub(r"\n?```$", "", content)
        try:
            parsed = json.loads(content)
            if not isinstance(parsed, list) or len(parsed) != len(batch):
                raise ValueError(f"Expected {len(batch)} items, got {len(parsed) if isinstance(parsed, list) else type(parsed)}")
            unique_results.extend(parsed)
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Batch parse failed (%s) -- single-coding %s responses", e, len(batch))
            for t in batch:
                unique_results.append(_code_single(client, t, codebook, project_cfg, coding_cfg, usage_log))

        logger.info("Coded %s/%s unique", min(i + batch_size, len(unique_texts)), len(unique_texts))
        if progress_cb is not None:
            progress_cb(batch_i, n_batches)

    return [unique_results[j] for j in idx_map]


def apply_codes(
    df: pd.DataFrame, codebook: Codebook, project_cfg: ProjectConfig, coding_cfg: CodingConfig, client: LLMClient,
    *, text_column: Optional[str] = None, progress_cb: Optional[ProgressCallback] = None, usage_log: Optional[list[dict]] = None,
) -> pd.DataFrame:
    """Apply `codebook` to every row of `df`. Adds code_<name> (0/1) and conf_<name> (0.0-1.0) columns.

    Rows that match no code are routed to the catch-all category if one exists.
    `progress_cb(batch_i, n_batches)` is called once per unique-text coding batch.
    """
    text_column = text_column or project_cfg.text_column
    df = df.copy()

    logger.info(
        "Coding %s responses (batch=%s, model=%s, compact_codebook=%s)...",
        len(df), coding_cfg.coding_batch_size, project_cfg.coding_model, coding_cfg.use_compact_codebook_for_coding,
    )
    results = _code_batch(client, df[text_column].tolist(), codebook, project_cfg, coding_cfg, progress_cb=progress_cb, usage_log=usage_log)

    for code in codebook.codes:
        df[f"code_{code.name}"] = 0
        df[f"conf_{code.name}"] = 0.0

    other_code = get_other_code_name(codebook, get_default_other_code_name(project_cfg))
    other_col = f"code_{other_code}" if other_code else None
    other_conf_col = f"conf_{other_code}" if other_code else None
    normalized_results = []

    for idx, res in zip(df.index, results):
        assigned = 0
        if not isinstance(res, dict):
            res = {"codes": []}
        invalid_codes = []

        for ci in res.get("codes", []):
            code_name = str(ci.get("code", "")).strip() if isinstance(ci, dict) else ""
            code_col = f"code_{code_name}"
            conf_col = f"conf_{code_name}"
            if code_name and code_col in df.columns:
                conf_value = _safe_confidence(ci.get("confidence", 0.0)) if isinstance(ci, dict) else 0.0
                df.at[idx, code_col] = 1
                df.at[idx, conf_col] = conf_value
                if isinstance(ci, dict):
                    ci["confidence"] = conf_value
                assigned += 1
            elif code_name:
                invalid_codes.append(code_name)

        if assigned == 0 and other_code and other_col in df.columns:
            df.at[idx, other_col] = 1
            df.at[idx, other_conf_col] = coding_cfg.other_fallback_confidence
            res = dict(res)
            res["codes"] = [{"code": other_code, "confidence": coding_cfg.other_fallback_confidence, "fallback": True}]
            res["fallback_reason"] = "No valid code matched; assigned catch-all category."
            if invalid_codes:
                res["invalid_returned_codes"] = invalid_codes

        normalized_results.append(res)

    df["coding_result"] = [json.dumps(r, ensure_ascii=False) for r in normalized_results]

    code_cols = [f"code_{c.name}" for c in codebook.codes]
    uncoded = int((df[code_cols].sum(axis=1) == 0).sum()) if code_cols else 0
    if uncoded:
        logger.warning("Coding complete with %s uncoded response(s).", uncoded)
    else:
        logger.info("Coding complete. No uncoded responses remain after fallback handling.")
    return df


def add_codes_column(df: pd.DataFrame, codebook: Codebook, separator: str = " | ") -> pd.DataFrame:
    """Rebuild codes / code_ids / num_codes / has_multi_label summary columns."""
    df = df.copy()
    for col in ["codes", "code_ids", "num_codes", "has_multi_label"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    entries = [(c.name, f"code_{c.name}") for c in codebook.codes if f"code_{c.name}" in df.columns]
    code_cols = [e[1] for e in entries]
    names = [e[0] for e in entries]
    id_by_name = {c.name: c.code_id for c in codebook.codes}

    df["codes_list"] = df.apply(lambda row: [n for n, c in zip(names, code_cols) if row[c] == 1], axis=1)
    df["code_ids_list"] = df["codes_list"].apply(lambda codes: [id_by_name.get(n, "") for n in codes if id_by_name.get(n, "")])
    df["codes"] = df["codes_list"].apply(lambda lst: separator.join(lst))
    df["code_ids"] = df["code_ids_list"].apply(lambda lst: separator.join(lst))
    df["num_codes"] = df["codes_list"].apply(len)
    df["has_multi_label"] = df["num_codes"] > 1
    return df.drop(columns=["codes_list", "code_ids_list"])
