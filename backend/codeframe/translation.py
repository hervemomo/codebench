"""Batch-translate detected-source-language responses into the target language.

Ported from notebook section 1-A.
"""

from __future__ import annotations

import json
import logging
import re
import time

import pandas as pd

from codeframe.config import CodingConfig, ProjectConfig
from codeframe.llm import LLMClient, chat_with_retry

logger = logging.getLogger(__name__)

# Errors that must never be swallowed by translation fallback logic.
_FATAL_ERRORS = (RuntimeError, KeyboardInterrupt, SystemExit)


def _translate_batch(
    client: LLMClient,
    texts: list[str],
    *,
    source_language_name: str,
    target_language_name: str,
    model: str,
    coding_cfg: CodingConfig,
) -> list[str]:
    """Translate a list of strings from source to target language in ONE API call."""
    numbered = "\n".join(f"[{i + 1}] {t}" for i, t in enumerate(texts))
    prompt = (
        f"Translate the following {len(texts)} survey responses "
        f"from {source_language_name.upper()} to {target_language_name.upper()}.\n\n"
        f"{numbered}\n\n"
        f"Return ONLY a JSON array with exactly {len(texts)} strings, "
        'preserving order. Example: ["translation 1", "translation 2"]'
    )
    resp = chat_with_retry(
        client,
        model=model,
        messages=[
            {"role": "system", "content": f"Translate to {target_language_name}. Return only a JSON array."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=min(4000, len(texts) * 120),
    )
    raw = re.sub(r"^```(?:json)?\n?", "", resp.choices[0].message.content.strip())
    raw = re.sub(r"\n?```$", "", raw)
    result = json.loads(raw)
    if not isinstance(result, list) or len(result) != len(texts):
        raise ValueError(f"Expected {len(texts)} translations, got {len(result)}")
    return [str(t).strip() for t in result]


def translate_records(
    df: pd.DataFrame,
    project_cfg: ProjectConfig,
    coding_cfg: CodingConfig,
    client: LLMClient,
    *,
    text_column: str = "cleaned_text",
    output_column: str | None = None,
    delay: float = 0.0,
) -> pd.DataFrame:
    """Translate rows whose `detected_lang` equals `project_cfg.source_language_code`.

    Rows in other detected languages are copied through unchanged. If source
    and target codes are equal, this is a no-op copy (no API calls).
    """
    output_column = output_column or project_cfg.text_column
    df = df.copy()
    df[output_column] = df[text_column]

    if project_cfg.source_language_code == project_cfg.target_language_code:
        logger.info("Source and target language are the same. Translation skipped.")
        return df

    source_name = project_cfg.language_name(project_cfg.source_language_code)
    target_name = project_cfg.language_name(project_cfg.target_language_code)

    source_idx = df[df["detected_lang"] == project_cfg.source_language_code].index.tolist()
    if not source_idx:
        logger.info("No %s responses to translate.", source_name)
        return df

    batch_size = coding_cfg.translation_batch_size
    n = len(source_idx)
    n_calls = -(-n // batch_size)
    logger.info("Translating %s %s responses to %s: %s API call(s) of %s texts each", n, source_name, target_name, n_calls, batch_size)

    for i in range(0, n, batch_size):
        batch_idx = source_idx[i : i + batch_size]
        batch_texts = df.loc[batch_idx, text_column].tolist()
        try:
            translated = _translate_batch(
                client, batch_texts,
                source_language_name=source_name, target_language_name=target_name,
                model=project_cfg.coding_model, coding_cfg=coding_cfg,
            )
            for idx, t in zip(batch_idx, translated):
                df.at[idx, output_column] = t
            logger.info("Translated %s/%s", min(i + batch_size, n), n)
        except _FATAL_ERRORS:
            raise
        except Exception as e:
            logger.warning("Batch parse failed (%s: %s); retrying %s responses one-by-one...", type(e).__name__, e, len(batch_idx))
            for idx in batch_idx:
                try:
                    r = _translate_batch(
                        client, [df.at[idx, text_column]],
                        source_language_name=source_name, target_language_name=target_name,
                        model=project_cfg.coding_model, coding_cfg=coding_cfg,
                    )
                    df.at[idx, output_column] = r[0]
                except _FATAL_ERRORS:
                    raise
                except Exception as e2:
                    logger.error("Translation failed for index %s (%s: %s). Original text kept as-is.", idx, type(e2).__name__, e2)
        if delay:
            time.sleep(delay)

    logger.info("Translation complete.")
    return df
