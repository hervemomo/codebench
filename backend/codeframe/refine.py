"""Split a code into sub-codes, or merge several codes into one.

Ported from notebook sections 4-B (split) and 5-B (merge). Both functions are
pure: they never mutate the `df`/`codebook` arguments and always return new
objects.
"""

from __future__ import annotations

import copy
import json
import logging
from typing import Optional

import pandas as pd

from codeframe.codebook import (
    Code,
    Codebook,
    apply_definition_fallbacks,
    canonical_code_key,
    clean_code_name,
    clean_optional_text,
    enrich_with_ai,
    get_default_other_code_name,
    get_other_code_name,
    validate_codebook,
)
from codeframe.codebook import auto_code_id_for_new_code, clean_code_id
from codeframe.coding import _code_batch, _safe_confidence, add_codes_column
from codeframe.config import CodingConfig, ProjectConfig
from codeframe.llm import LLMClient, chat_with_retry, extract_json

logger = logging.getLogger(__name__)


def _normalize_manual_id_list(values, expected_len: int, label: str) -> list[str]:
    values = values or []
    ids = [clean_code_id(x) for x in values]
    if ids and len(ids) != expected_len:
        raise ValueError(f"{label} must be blank or have exactly {expected_len} item(s).")
    if not ids:
        ids = [""] * expected_len
    return ids


def split_code(
    df: pd.DataFrame,
    codebook: Codebook,
    client: LLMClient,
    parent_code: str,
    project_cfg: ProjectConfig,
    coding_cfg: CodingConfig,
    *,
    subcodes: Optional[list[str]] = None,
    subcode_ids: Optional[list[str]] = None,
    subcode_definitions: Optional[list[str]] = None,
    n_subcodes_proposed: int = 3,
    enrich_subcodes: bool = True,
    text_column: Optional[str] = None,
    preserve_parent: bool = False,
    usage_log: Optional[list[dict]] = None,
) -> tuple[pd.DataFrame, Codebook]:
    """Split `parent_code` into two or more finer sub-codes. Pure: returns new (df, codebook)."""
    text_column = text_column or project_cfg.text_column
    subcodes = subcodes or []
    subcode_ids = subcode_ids or []
    subcode_definitions = subcode_definitions or []

    df = df.copy()
    codebook = copy.deepcopy(codebook)

    parent_entry = codebook.get_code(parent_code)
    if parent_entry is None:
        raise ValueError(f'"{parent_code}" not in codebook. Available: {[c.name for c in codebook.codes]}')

    requires_ids = codebook.requires_manual_ids()
    split_source = "manual_split" if subcodes else "ai_split_proposal"

    # 1. Determine sub-code names.
    if subcodes and len(subcodes) >= 2:
        final_names = [clean_code_name(s) for s in subcodes if clean_code_name(s)]
    else:
        parent_col = f"code_{parent_code}"
        if parent_col not in df.columns:
            raise KeyError(f'"{parent_col}" not found. Run coding first.')
        affected = df.loc[df[parent_col] == 1, text_column].tolist()
        if len(affected) < 2:
            raise ValueError(f'Only {len(affected)} response(s) carry "{parent_code}". Need >= 2 to split.')
        sample = affected[:30]
        verbatims = "\n".join(f'{i + 1}. "{r}"' for i, r in enumerate(sample))
        lang_name = project_cfg.codebook_language_name
        ctx = project_cfg.survey_context
        prompt = (
            "You are a qualitative research expert.\n\n"
            f"CODEBOOK OUTPUT LANGUAGE: {lang_name}.\nGenerate the sub-code names in {lang_name}.\n\n"
            f"CONTEXT: {ctx}\n\n"
            f'The code "{parent_code}" is too broad. Here are {len(sample)} responses assigned to it:\n{verbatims}\n\n'
            f"Propose exactly {n_subcodes_proposed} distinct and mutually exclusive sub-codes with short names in {lang_name}.\n"
            'Return ONLY valid JSON:\n{"subcodes": ["Name 1", "Name 2", "..."]}'
        )
        resp = chat_with_retry(
            client, model=project_cfg.reasoning_model,
            messages=[{"role": "system", "content": "Qualitative coding expert. Return ONLY valid JSON."}, {"role": "user", "content": prompt}],
            temperature=0.4, max_tokens=500, timeout=project_cfg.openai_timeout_seconds,
            max_retries=project_cfg.openai_max_retries, usage_log=usage_log,
        )
        try:
            final_names = [s.strip() for s in json.loads(extract_json(resp.choices[0].message.content.strip())).get("subcodes", []) if s.strip()]
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Sub-code proposal parse error: %s", e)
            final_names = []
        if not final_names:
            raise ValueError("Model returned no sub-codes. Provide `subcodes` manually.")

    if len(final_names) < 2:
        raise ValueError("Need >= 2 sub-codes to split.")
    if len({s.lower() for s in final_names}) != len(final_names):
        raise ValueError(f"Duplicate sub-code names are not allowed: {final_names}")

    existing_names_lower = {c.name.lower() for c in codebook.codes if c.name.lower() != parent_code.lower()}
    collisions = [s for s in final_names if s.lower() in existing_names_lower]
    if collisions:
        raise ValueError(f"Sub-code name(s) already exist in the codebook: {collisions}.")

    # 2. Determine sub-code IDs.
    manual_ids = _normalize_manual_id_list(subcode_ids, len(final_names), "subcode_ids")
    if requires_ids:
        existing_ids = codebook.existing_code_ids()
        parent_prefix = parent_entry.code_id or clean_code_name(parent_code)
        final_ids = []
        for name, manual_id in zip(final_names, manual_ids):
            if manual_id:
                if manual_id in existing_ids:
                    raise ValueError(f"subcode_ids contains an ID already in the codebook: {manual_id}")
                existing_ids.add(manual_id)
                final_ids.append(manual_id)
            else:
                final_ids.append(auto_code_id_for_new_code(codebook, name, prefix=parent_prefix, existing_ids=existing_ids))
    else:
        final_ids = [""] * len(final_names)
    if final_ids and len({x for x in final_ids if x}) != len([x for x in final_ids if x]):
        raise ValueError(f"Duplicate sub-code IDs are not allowed: {final_ids}")

    # 3. Determine definitions.
    final_defs = [clean_optional_text(x) for x in subcode_definitions]
    if final_defs and len(final_defs) != len(final_names):
        raise ValueError("subcode_definitions must be blank or have the same length as subcodes.")
    if not final_defs:
        final_defs = [""] * len(final_names)
    missing_defs = [n for n, d in zip(final_names, final_defs) if not d]
    if missing_defs and not enrich_subcodes:
        raise ValueError(f"Split-derived codes require definitions. Missing definitions for: {missing_defs}")

    # 4. Build sub-code codebook.
    sub_codebook = Codebook(
        version="split-draft", multi_label=codebook.multi_label,
        codes=[
            Code(name=n, code_id=cid, definition=d, parent_code=parent_code, parent_code_id=parent_entry.code_id, source=split_source)
            for n, cid, d in zip(final_names, final_ids, final_defs)
        ],
    )
    validate_codebook(sub_codebook)

    # 5. Enrich missing definitions, with deterministic fallback.
    if enrich_subcodes:
        sub_codebook = enrich_with_ai(
            client, sub_codebook, project_cfg, coding_cfg,
            fill_missing_with_fallback=True, fallback_parent_code=parent_code, usage_log=usage_log,
        )
    else:
        sub_codebook = apply_definition_fallbacks(project_cfg, sub_codebook, parent_code=parent_code)

    # 6. Re-code only the affected rows.
    parent_col = f"code_{parent_code}"
    affected_idx = df[df[parent_col] == 1].index
    if len(affected_idx) > 0:
        for sc in sub_codebook.codes:
            df[f"code_{sc.name}"] = 0
            df[f"conf_{sc.name}"] = 0.0

        other_code = get_other_code_name(codebook, get_default_other_code_name(project_cfg))
        other_col = f"code_{other_code}" if other_code else None
        other_conf_col = f"conf_{other_code}" if other_code else None

        results = _code_batch(client, df.loc[affected_idx, text_column].tolist(), sub_codebook, project_cfg, coding_cfg, usage_log=usage_log)
        for idx, rv in zip(affected_idx, results):
            assigned = 0
            if not isinstance(rv, dict):
                rv = {"codes": []}
            for ci in rv.get("codes", []):
                if not isinstance(ci, dict):
                    continue
                code_name = str(ci.get("code", "")).strip()
                code_col = f"code_{code_name}"
                if code_name and code_col in df.columns:
                    conf_value = _safe_confidence(ci.get("confidence", 0.0))
                    df.at[idx, code_col] = 1
                    df.at[idx, f"conf_{code_name}"] = conf_value
                    assigned += 1
            if assigned == 0 and other_col and other_col in df.columns:
                df.at[idx, other_col] = 1
                df.at[idx, other_conf_col] = coding_cfg.other_fallback_confidence

    # 7. Preserve or remove parent columns.
    if not preserve_parent:
        df = df.drop(columns=[c for c in [f"code_{parent_code}", f"conf_{parent_code}"] if c in df.columns])

    # 8. Update codebook.
    new_codes: list[Code] = []
    inserted = False
    for code in codebook.codes:
        if code.name == parent_code:
            if preserve_parent:
                new_codes.append(code)
            new_codes.extend(sub_codebook.codes)
            inserted = True
        else:
            new_codes.append(code)
    if not inserted:
        raise ValueError(f'"{parent_code}" not found during codebook update.')

    updated_codebook = Codebook(
        codes=new_codes, version=f"{codebook.version}+split", multi_label=codebook.multi_label,
        description=codebook.description, codebook_language=codebook.codebook_language,
        generated_at=codebook.generated_at, model=codebook.model,
        code_id_column=codebook.code_id_column, definition_column=codebook.definition_column,
    )
    validate_codebook(updated_codebook)

    df = add_codes_column(df, updated_codebook)
    logger.info('Split complete: "%s" -> %s', parent_code, final_names)
    return df, updated_codebook


def merge_codes(
    df: pd.DataFrame,
    codebook: Codebook,
    client: LLMClient,
    codes_to_merge: list[str],
    project_cfg: ProjectConfig,
    coding_cfg: CodingConfig,
    *,
    merged_name: str = "",
    merged_code_id: str = "",
    merged_definition: str = "",
    enrich_merged: bool = True,
    text_column: Optional[str] = None,
    usage_log: Optional[list[dict]] = None,
) -> tuple[pd.DataFrame, Codebook]:
    """Merge two or more codes into one consolidated code. Pure: returns new (df, codebook)."""
    text_column = text_column or project_cfg.text_column
    if len(codes_to_merge) < 2:
        raise ValueError("Need >= 2 codes to merge.")

    df = df.copy()
    codebook = copy.deepcopy(codebook)

    cb_names = [c.name for c in codebook.codes]
    missing = [c for c in codes_to_merge if c not in cb_names]
    if missing:
        raise ValueError(f"Not in codebook: {missing}. Available: {cb_names}")

    requires_ids = codebook.requires_manual_ids()
    merged_code_id = clean_code_id(merged_code_id)
    merged_definition = clean_optional_text(merged_definition)

    # 1. Determine merged code name + initial definition.
    if merged_name.strip():
        final_name, final_def = merged_name.strip(), merged_definition
    else:
        summaries = []
        for name in codes_to_merge:
            entry = codebook.get_code(name)
            no_def = "(no definition)" if project_cfg.codebook_is_english else "(pas de définition)"
            summaries.append(f"- **{entry.ref() if entry else name}** : {entry.definition if entry and entry.definition else no_def}")
        lang_name = project_cfg.codebook_language_name
        prompt = (
            "You are a qualitative research expert.\n\n"
            f"CODEBOOK OUTPUT LANGUAGE: {lang_name}.\nGenerate the merged code name and definition in {lang_name}.\n\n"
            f"CONTEXT: {project_cfg.survey_context}\n\n"
            f"The following codes will be merged:\n{chr(10).join(summaries)}\n\n"
            f"Propose a short name (max 5 words) and a 1-2 sentence definition in {lang_name}.\n"
            'Return ONLY valid JSON:\n{"name": "...", "definition": "..."}'
        )
        resp = chat_with_retry(
            client, model=project_cfg.reasoning_model,
            messages=[{"role": "system", "content": "Qualitative coding expert. Return ONLY valid JSON."}, {"role": "user", "content": prompt}],
            temperature=0.3, max_tokens=300, timeout=project_cfg.openai_timeout_seconds,
            max_retries=project_cfg.openai_max_retries, usage_log=usage_log,
        )
        try:
            parsed = json.loads(extract_json(resp.choices[0].message.content.strip()))
            final_name = parsed.get("name", "").strip()
            final_def = clean_optional_text(parsed.get("definition", ""))
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.error("Merge name proposal parse error: %s", e)
            final_name, final_def = "", ""
        if not final_name:
            raise ValueError("Model returned no name. Provide `merged_name` manually.")
        if merged_definition:
            final_def = merged_definition

    existing_target_keys = {canonical_code_key(c.name) for c in codebook.codes if c.name not in codes_to_merge}
    if canonical_code_key(final_name) in existing_target_keys:
        raise ValueError(f'Merged code name "{final_name}" already exists outside the source group.')

    # 2. Determine merged code ID.
    source_entries = [c for c in codebook.codes if c.name in codes_to_merge]
    merged_from_ids = [c.code_id for c in source_entries if c.code_id]
    if requires_ids:
        existing_ids = codebook.existing_code_ids()
        if merged_code_id:
            if merged_code_id in existing_ids:
                raise ValueError(f"merged_code_id already exists in the codebook: {merged_code_id}")
        else:
            merged_code_id = auto_code_id_for_new_code(codebook, final_name, prefix="MERGE", existing_ids=existing_ids)
    else:
        merged_code_id = ""

    # 3. Require or generate definition.
    if not final_def and not enrich_merged:
        raise ValueError("Merge-derived code requires a definition, or set enrich_merged=True.")

    merged_entry = Code(
        name=final_name, code_id=merged_code_id, definition=final_def,
        merged_from=list(codes_to_merge), merged_from_ids=merged_from_ids,
        source="manual_merge" if merged_name.strip() else "ai_merge_proposal",
    )

    # 4. Optionally enrich, then deterministic fallback if still blank.
    if enrich_merged and not clean_optional_text(merged_entry.definition):
        mini = Codebook(codes=[merged_entry], multi_label=codebook.multi_label)
        mini = enrich_with_ai(client, mini, project_cfg, coding_cfg, fill_missing_with_fallback=True, fallback_merged_from=codes_to_merge, usage_log=usage_log)
        merged_entry = mini.codes[0]
    if not clean_optional_text(merged_entry.definition):
        mini = Codebook(codes=[merged_entry], multi_label=codebook.multi_label)
        mini = apply_definition_fallbacks(project_cfg, mini, merged_from=codes_to_merge)
        merged_entry = mini.codes[0]

    # 5. Deterministic OR-merge (no LLM re-coding).
    source_code_cols = [f"code_{c}" for c in codes_to_merge]
    source_conf_cols = [f"conf_{c}" for c in codes_to_merge]
    missing_cols = [c for c in source_code_cols if c not in df.columns]
    if missing_cols:
        raise KeyError(f"Columns not found: {missing_cols}. Run coding first.")

    df[f"code_{final_name}"] = df[source_code_cols].max(axis=1).astype(int)
    existing_conf_cols = [c for c in source_conf_cols if c in df.columns]
    df[f"conf_{final_name}"] = df[existing_conf_cols].max(axis=1) if existing_conf_cols else df[f"code_{final_name}"].astype(float)
    df = df.drop(columns=[c for c in source_code_cols + source_conf_cols if c in df.columns])

    # 6. Update codebook: replace sources with the merged entry at the first source position.
    new_codes: list[Code] = []
    inserted = False
    for code in codebook.codes:
        if code.name in codes_to_merge:
            if not inserted:
                new_codes.append(merged_entry)
                inserted = True
        else:
            new_codes.append(code)
    if not inserted:
        raise ValueError(f"None of {codes_to_merge} found in codebook.")

    updated_codebook = Codebook(
        codes=new_codes, version=f"{codebook.version}+merge", multi_label=codebook.multi_label,
        description=codebook.description, codebook_language=codebook.codebook_language,
        generated_at=codebook.generated_at, model=codebook.model,
        code_id_column=codebook.code_id_column, definition_column=codebook.definition_column,
    )
    validate_codebook(updated_codebook)

    df = add_codes_column(df, updated_codebook)
    logger.info("Merge complete: %s -> %s", codes_to_merge, final_name)
    return df, updated_codebook
