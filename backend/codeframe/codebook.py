"""Codebook data model, AI generation, user-supplied loading, and AI enrichment.

Ported from notebook sections 0-E, 2-B, 3-B.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from codeframe.config import CodingConfig, ProjectConfig
from codeframe.llm import LLMClient, chat_with_retry, extract_json

logger = logging.getLogger(__name__)

CODE_ID_FIELD = "code_id"


# ── Code / Codebook data model ──────────────────────────────────────────────


@dataclass
class Code:
    name: str
    code_id: str = ""
    definition: str = ""
    inclusion_criteria: list[str] = field(default_factory=list)
    exclusion_criteria: list[str] = field(default_factory=list)
    example_verbatims: list[str] = field(default_factory=list)
    parent_code: str = ""
    parent_code_id: str = ""
    merged_from: list[str] = field(default_factory=list)
    merged_from_ids: list[str] = field(default_factory=list)
    source: str = ""
    definition_source: str = ""

    def ref(self) -> str:
        return f"[{self.code_id}] {self.name}" if self.code_id else self.name

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "definition": self.definition,
            "inclusion_criteria": self.inclusion_criteria,
            "exclusion_criteria": self.exclusion_criteria,
            "example_verbatims": self.example_verbatims,
        }
        if self.code_id:
            d[CODE_ID_FIELD] = self.code_id
        for k in ("parent_code", "parent_code_id", "source", "definition_source"):
            v = getattr(self, k)
            if v:
                d[k] = v
        if self.merged_from:
            d["merged_from"] = self.merged_from
        if self.merged_from_ids:
            d["merged_from_ids"] = self.merged_from_ids
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Code":
        return cls(
            name=clean_code_name(d.get("name", "")),
            code_id=clean_code_id(d.get(CODE_ID_FIELD, "")),
            definition=clean_optional_text(d.get("definition", "")),
            inclusion_criteria=list(d.get("inclusion_criteria", []) or []),
            exclusion_criteria=list(d.get("exclusion_criteria", []) or []),
            example_verbatims=list(d.get("example_verbatims", []) or []),
            parent_code=d.get("parent_code", "") or "",
            parent_code_id=d.get("parent_code_id", "") or "",
            merged_from=list(d.get("merged_from", []) or []),
            merged_from_ids=list(d.get("merged_from_ids", []) or []),
            source=d.get("source", "") or "",
            definition_source=d.get("definition_source", "") or "",
        )


@dataclass
class Codebook:
    codes: list[Code] = field(default_factory=list)
    version: str = "1.0"
    multi_label: bool = True
    description: str = ""
    codebook_language: str = "fr"
    generated_at: Optional[str] = None
    model: Optional[str] = None
    code_id_column: Optional[str] = None
    definition_column: Optional[str] = None

    def has_code_ids(self) -> bool:
        return any(c.code_id for c in self.codes)

    def requires_manual_ids(self) -> bool:
        return self.has_code_ids()

    def get_code(self, name: str) -> Optional[Code]:
        return next((c for c in self.codes if c.name == name), None)

    def existing_code_ids(self) -> set[str]:
        return {c.code_id for c in self.codes if c.code_id}

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "multi_label": self.multi_label,
            "description": self.description,
            "codebook_language": self.codebook_language,
            "generated_at": self.generated_at,
            "model": self.model,
            "code_id_column": self.code_id_column,
            "definition_column": self.definition_column,
            "codes": [c.to_dict() for c in self.codes],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Codebook":
        return cls(
            codes=[Code.from_dict(c) for c in d.get("codes", [])],
            version=d.get("version", "1.0"),
            multi_label=d.get("multi_label", True),
            description=d.get("description", "") or "",
            codebook_language=d.get("codebook_language", "fr") or "fr",
            generated_at=d.get("generated_at"),
            model=d.get("model"),
            code_id_column=d.get("code_id_column"),
            definition_column=d.get("definition_column"),
        )


def save_codebook(codebook: Codebook, filepath: str | Path) -> None:
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(codebook.to_dict(), f, indent=2, ensure_ascii=False)


def load_codebook(filepath: str | Path) -> Codebook:
    with open(filepath, encoding="utf-8") as f:
        return Codebook.from_dict(json.load(f))


# ── Cleaning / normalisation helpers ────────────────────────────────────────


def clean_code_id(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def clean_code_name(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def clean_optional_text(value) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def canonical_code_key(value) -> str:
    """Match AI-returned code names ("Name" or "[ID] Name") back to codebook entries."""
    text = clean_code_name(value)
    text = re.sub(r"^\[[^\]]+\]\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.casefold()


def _slugify_for_code_id(value, default: str = "CODE", max_len: int = 48) -> str:
    text = clean_code_name(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_").upper()
    text = re.sub(r"_+", "_", text)
    if not text:
        text = default or ""
    return text[:max_len].strip("_") or default or ""


def _make_unique_code_id(base: str, existing_ids: set[str], max_len: int = 64) -> str:
    base = _slugify_for_code_id(base, default="CODE", max_len=max_len) or "CODE"
    candidate = base
    i = 2
    while candidate in existing_ids:
        suffix = f"_{i:02d}"
        candidate = f'{base[: max_len - len(suffix)].rstrip("_")}{suffix}'
        i += 1
    existing_ids.add(candidate)
    return candidate


def auto_code_id_for_new_code(codebook: Codebook, code_name: str, *, prefix: str = "", existing_ids: Optional[set[str]] = None) -> str:
    if existing_ids is None:
        existing_ids = codebook.existing_code_ids()
    prefix = _slugify_for_code_id(prefix, default="", max_len=24) if prefix else ""
    name_part = _slugify_for_code_id(code_name, default="CODE", max_len=40)
    base = f"{prefix}_{name_part}" if prefix else name_part
    return _make_unique_code_id(base, existing_ids)


def get_default_other_code_name(project_cfg: ProjectConfig) -> str:
    if project_cfg.codebook_is_english:
        return "Other / Not classifiable"
    return "Autre / Non classifiable"


def _default_other_code_metadata(project_cfg: ProjectConfig, other_name: Optional[str] = None) -> dict:
    if other_name is None:
        other_name = get_default_other_code_name(project_cfg)
    if project_cfg.codebook_is_english:
        return {
            "definition": "Valid response that does not clearly match any other code in the codebook.",
            "inclusion_criteria": [
                "Use only when no specific code applies.",
                "Use for ambiguous, off-topic, or non-classifiable responses.",
            ],
            "exclusion_criteria": [
                "Do not use if a more specific code applies.",
                "Do not use for blank or invalid responses already removed during preprocessing.",
            ],
        }
    return {
        "definition": "Réponse valide qui ne correspond clairement à aucun autre code du livre de codes.",
        "inclusion_criteria": [
            "Utiliser seulement lorsqu'aucun code spécifique ne s'applique.",
            "Utiliser pour les réponses ambiguës, hors sujet ou non classifiables.",
        ],
        "exclusion_criteria": [
            "Ne pas utiliser si un code plus spécifique s'applique.",
            "Ne pas utiliser pour les réponses vides ou invalides déjà retirées au prétraitement.",
        ],
    }


def _fallback_code_definition(project_cfg: ProjectConfig, code_name: str, *, parent_code: str = "", merged_from: Optional[list[str]] = None) -> str:
    """Deterministic fallback definition used when AI enrichment does not return one."""
    name = clean_code_name(code_name)
    parent = clean_code_name(parent_code)
    if project_cfg.codebook_is_english:
        if merged_from:
            merged = ", ".join(clean_code_name(x) for x in merged_from if clean_code_name(x))
            return f'Responses grouped under "{name}", consolidating ideas previously coded as: {merged}.'
        if parent:
            return f'Responses related to the sub-theme "{name}" within the parent code "{parent}".'
        return f'Responses associated with the theme "{name}".'
    if merged_from:
        merged = ", ".join(clean_code_name(x) for x in merged_from if clean_code_name(x))
        return f'Réponses regroupées sous « {name} », consolidant les idées auparavant codées comme : {merged}.'
    if parent:
        return f'Réponses relevant du sous-thème « {name} » dans le code parent « {parent} ».'
    return f'Réponses associées au thème « {name} ».'


def apply_definition_fallbacks(project_cfg: ProjectConfig, codebook: Codebook, *, parent_code: str = "", merged_from: Optional[list[str]] = None) -> Codebook:
    """Fill any remaining blank definitions with deterministic fallback text."""
    for code in codebook.codes:
        if not clean_optional_text(code.definition):
            code.definition = _fallback_code_definition(project_cfg, code.name, parent_code=parent_code, merged_from=merged_from)
            code.definition_source = "deterministic_fallback"
            if not code.inclusion_criteria:
                code.inclusion_criteria = [f'The verbatim clearly matches the theme "{code.name}".']
            if not code.exclusion_criteria:
                code.exclusion_criteria = ["Do not use if a more specific code applies."]
    return codebook


def validate_codebook(codebook: Codebook) -> None:
    if not codebook.codes:
        raise ValueError("Codebook has no codes.")
    names: list[str] = []
    ids: list[str] = []
    has_ids = codebook.has_code_ids()
    for i, code in enumerate(codebook.codes):
        name = clean_code_name(code.name)
        if not name:
            raise ValueError(f"Code #{i + 1} has a blank name.")
        names.append(name)
        if has_ids:
            if not code.code_id:
                raise ValueError(f'Code "{name}" is missing code_id. Every code must have an ID once any code has one.')
            ids.append(code.code_id)
    dup_names = sorted({n for n in names if names.count(n) > 1})
    if dup_names:
        raise ValueError(f"Duplicate code names are not supported because columns are name-based: {dup_names}")
    if has_ids:
        dup_ids = sorted({x for x in ids if ids.count(x) > 1})
        if dup_ids:
            raise ValueError(f"Duplicate code IDs found: {dup_ids}")


def get_other_code_name(codebook: Codebook, preferred_name: str) -> Optional[str]:
    preferred_norm = preferred_name.strip().lower()
    for code in codebook.codes:
        if code.name.strip().lower() == preferred_norm:
            return code.name
    return None


def ensure_other_code(project_cfg: ProjectConfig, codebook: Codebook, other_name: Optional[str] = None, other_code_id: str = "") -> Codebook:
    """Ensure a catch-all category exists in the codebook."""
    if other_name is None:
        other_name = get_default_other_code_name(project_cfg)

    if get_other_code_name(codebook, other_name) is not None:
        validate_codebook(codebook)
        return codebook

    if codebook.requires_manual_ids() and not clean_code_id(other_code_id):
        raise ValueError(f'Catch-all code "{other_name}" is missing and this codebook requires code IDs; provide other_code_id.')

    meta = _default_other_code_metadata(project_cfg, other_name)
    codebook.codes.append(Code(
        name=other_name, code_id=clean_code_id(other_code_id), definition=meta["definition"],
        inclusion_criteria=meta["inclusion_criteria"], exclusion_criteria=meta["exclusion_criteria"],
        source="system_catch_all",
    ))
    validate_codebook(codebook)
    logger.info("Added catch-all code: %s", other_name)
    return codebook


# ── Prompt rendering ─────────────────────────────────────────────────────────


def to_full_prompt(codebook: Codebook) -> str:
    """Render a codebook as a numbered text block for an LLM prompt."""
    lines = []
    for i, code in enumerate(codebook.codes, 1):
        lines.append(f"{i}. **{code.ref()}**")
        if code.definition:
            lines.append(f"   Definition: {code.definition}")
        if code.inclusion_criteria:
            lines.append(f"   Include if: {'; '.join(code.inclusion_criteria)}")
        if code.exclusion_criteria:
            lines.append(f"   Exclude if: {'; '.join(code.exclusion_criteria)}")
        lines.append("")
    return "\n".join(lines)


def to_compact_prompt(codebook: Codebook) -> str:
    """Render a shorter codebook (names + definitions only) for high-volume coding calls."""
    lines = []
    for i, code in enumerate(codebook.codes, 1):
        ref = code.ref()
        lines.append(f"{i}. {ref}: {code.definition}" if code.definition else f"{i}. {ref}")
    return "\n".join(lines)


def _fmt_clusters(representatives: dict[int, list[str]]) -> str:
    lines = []
    for cid, samples in representatives.items():
        lines.append(f"\n### Cluster {cid + 1}")
        for i, s in enumerate(samples, 1):
            lines.append(f'{i}. "{s}"')
    return "\n".join(lines)


# ── AI codebook generation ──────────────────────────────────────────────────


def generate_codebook(
    client: LLMClient,
    representatives: dict[int, list[str]],
    project_cfg: ProjectConfig,
    coding_cfg: CodingConfig,
    *,
    target_codes: Optional[int] = None,
    multi_label: bool = True,
    usage_log: Optional[list[dict]] = None,
) -> Codebook:
    """Generate a codebook from cluster representatives, with a truncation-JSON retry."""
    ctx = project_cfg.survey_context or "Open-ended survey responses."
    lang_name = project_cfg.codebook_language_name
    other_name = get_default_other_code_name(project_cfg)
    count_instruction = f"Create exactly {target_codes} distinct codes" if target_codes else "Create an appropriate number of distinct codes"
    label_instruction = "The codes must support multi-label coding." if multi_label else "The codes must be mutually exclusive."

    base_msg = (
        "Analyze the groups and create a qualitative codebook.\n\n"
        f"CODEBOOK OUTPUT LANGUAGE: {lang_name}.\n"
        f"Write code names, definitions, criteria, example verbatims, and the catch-all code in {lang_name}.\n\n"
        f"CONTEXT:\n{ctx}\n\nGROUPS:\n{_fmt_clusters(representatives)}\n\n"
        f"INSTRUCTIONS:\n1. {count_instruction}.\n2. {label_instruction}\n"
        "3. Merge groups whose themes overlap.\n"
        f'4. Add this exact catch-all code: "{other_name}".\n'
        "Return ONLY valid JSON, with no Markdown and no text outside JSON:\n"
        '{"codes":[{"name":"...","definition":"...",'
        '"inclusion_criteria":["..."],"exclusion_criteria":["..."],'
        '"example_verbatims":["..."]}]}'
    )

    first_budget = coding_cfg.codebook_generation_max_tokens
    retry_budget = coding_cfg.codebook_generation_retry_max_tokens
    token_budgets = [first_budget]
    if retry_budget and retry_budget > first_budget:
        token_budgets.append(retry_budget)

    last_error: Optional[Exception] = None
    last_raw = ""

    for attempt, token_budget in enumerate(token_budgets, 1):
        retry_note = ""
        if attempt > 1:
            retry_note = (
                "\n\nIMPORTANT RETRY INSTRUCTION:\n"
                "The previous response was truncated or invalid JSON. Return a shorter, "
                "complete JSON object. Keep all text very concise and do not include markdown."
            )
        resp = chat_with_retry(
            client, model=project_cfg.reasoning_model,
            messages=[
                {"role": "system", "content": "Qualitative research expert. Return ONLY complete valid JSON."},
                {"role": "user", "content": base_msg + retry_note},
            ],
            temperature=0.3, max_tokens=token_budget,
            timeout=project_cfg.openai_timeout_seconds, max_retries=project_cfg.openai_max_retries,
            usage_log=usage_log,
        )
        choice = resp.choices[0]
        finish_reason = getattr(choice, "finish_reason", "")
        last_raw = (choice.message.content or "").strip()

        try:
            if finish_reason == "length":
                raise json.JSONDecodeError(f"LLM output stopped because max_tokens={token_budget} was reached", last_raw, len(last_raw))
            parsed = json.loads(extract_json(last_raw))
            cb = Codebook.from_dict(parsed)
            validate_codebook(cb)
            cb = ensure_other_code(project_cfg, cb, other_name=other_name)
            cb.version = "1.0-draft"
            cb.description = project_cfg.survey_context
            cb.multi_label = multi_label
            cb.codebook_language = project_cfg.codebook_language_code
            cb.generated_at = datetime.now(timezone.utc).isoformat()
            cb.model = project_cfg.reasoning_model
            logger.info("Codebook generated: %s codes.", len(cb.codes))
            return cb
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            last_error = e
            logger.warning("Codebook JSON parse/validation failed on attempt %s/%s: %s", attempt, len(token_budgets), e)

    tail = (last_raw or "")[-800:]
    raise ValueError(
        "Codebook generation returned truncated or invalid JSON after automatic retry. "
        f"Last error: {last_error}\n\nLast output tail for debugging:\n{tail}"
    )


# ── User-supplied codebook loading ──────────────────────────────────────────


def _definition_from_dict(item: dict) -> str:
    return clean_optional_text(
        item.get("definition") or item.get("Definition") or item.get("Définition")
        or item.get("Code Definition") or item.get("code_definition") or ""
    )


def _entry_from_row(row, name_col, id_col=None, definition_col=None) -> Optional[Code]:
    name = clean_code_name(row[name_col])
    if not name:
        return None
    code_id = clean_code_id(row[id_col]) if id_col else ""
    if id_col and not code_id:
        raise ValueError(f'Code "{name}" is missing an ID in column "{id_col}".')
    definition = clean_optional_text(row[definition_col]) if definition_col else ""
    return Code(name=name, code_id=code_id, definition=definition, source="user_codebook")


def load_user_codebook(
    source: str | Path | list, *, name_column: Optional[str] = None, id_column: Optional[str] = None,
    definition_column: Optional[str] = None, sheet_name: int | str = 0,
) -> Codebook:
    """Load a user-supplied codebook from xlsx/csv/json/txt or a Python list."""
    entries: list[Code] = []

    if isinstance(source, list):
        for item in source:
            if isinstance(item, dict):
                name = clean_code_name(item.get("name") or item.get("Code Name") or item.get("code"))
                code_id = clean_code_id(item.get(CODE_ID_FIELD) or item.get("Code ID") or item.get("id"))
                if name:
                    entries.append(Code(
                        name=name, code_id=code_id, definition=_definition_from_dict(item),
                        inclusion_criteria=list(item.get("inclusion_criteria", []) or []),
                        exclusion_criteria=list(item.get("exclusion_criteria", []) or []),
                        example_verbatims=list(item.get("example_verbatims", []) or []),
                        source="user_codebook",
                    ))
            else:
                name = clean_code_name(item)
                if name:
                    entries.append(Code(name=name, source="user_codebook"))
    elif isinstance(source, (str, Path)):
        path = Path(source)
        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            df_ = pd.read_excel(path, sheet_name=sheet_name)
        elif suffix == ".csv":
            df_ = pd.read_csv(path)
        elif suffix == ".json":
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                if isinstance(item, dict):
                    name = clean_code_name(item.get("name") or item.get("Code Name") or item.get("code"))
                    code_id = clean_code_id(item.get(CODE_ID_FIELD) or item.get("Code ID") or item.get("id"))
                    if name:
                        entries.append(Code(
                            name=name, code_id=code_id, definition=_definition_from_dict(item),
                            inclusion_criteria=list(item.get("inclusion_criteria", []) or []),
                            exclusion_criteria=list(item.get("exclusion_criteria", []) or []),
                            example_verbatims=list(item.get("example_verbatims", []) or []),
                            source="user_codebook",
                        ))
                else:
                    name = clean_code_name(item)
                    if name:
                        entries.append(Code(name=name, source="user_codebook"))
            df_ = None
        elif suffix == ".txt":
            if id_column or definition_column:
                raise ValueError("Plain text codebooks cannot preserve IDs or definitions. Use Excel, CSV, or JSON.")
            with open(path, encoding="utf-8") as f:
                entries = [Code(name=line.strip(), source="user_codebook") for line in f if line.strip()]
            df_ = None
        else:
            raise ValueError(f"Unsupported format: {suffix}")

        if suffix in (".xlsx", ".xls", ".csv"):
            col = name_column or df_.columns[0]
            if col not in df_.columns:
                raise ValueError(f'name_column "{col}" not found. Available columns: {list(df_.columns)}')
            if id_column and id_column not in df_.columns:
                raise ValueError(f'id_column "{id_column}" not found. Available columns: {list(df_.columns)}')
            if definition_column and definition_column not in df_.columns:
                raise ValueError(f'definition_column "{definition_column}" not found. Available columns: {list(df_.columns)}')
            for _, row in df_.dropna(subset=[col]).iterrows():
                entry = _entry_from_row(row, col, id_column, definition_column)
                if entry:
                    entries.append(entry)
    else:
        raise TypeError("source must be a file path or a list of code names/dicts.")

    if not entries:
        raise ValueError("No codes found. Check your file and name_column.")

    seen_names: set[str] = set()
    unique: list[Code] = []
    for entry in entries:
        key = entry.name.strip().lower()
        if key in seen_names:
            raise ValueError(f'Duplicate code name found: "{entry.name}". Code names must be unique.')
        seen_names.add(key)
        unique.append(entry)

    codebook = Codebook(
        codes=unique, version="user-supplied", multi_label=True,
        code_id_column=id_column, definition_column=definition_column,
    )
    validate_codebook(codebook)
    logger.info("Loaded %s codes. code_ids_preserved=%s", len(unique), codebook.has_code_ids())
    return codebook


# ── AI enrichment ────────────────────────────────────────────────────────────


def enrich_with_ai(
    client: LLMClient, codebook: Codebook, project_cfg: ProjectConfig, coding_cfg: CodingConfig,
    *, fill_missing_with_fallback: bool = False, fallback_parent_code: str = "",
    fallback_merged_from: Optional[list[str]] = None, usage_log: Optional[list[dict]] = None,
) -> Codebook:
    """Write definitions/criteria/verbatims for codes with an empty definition, in one API call."""
    to_enrich = [c for c in codebook.codes if not clean_optional_text(c.definition)]
    if not to_enrich:
        logger.info("All codes have definitions -- skipping enrichment.")
        return codebook

    logger.info("Enriching %s codes (1 API call)...", len(to_enrich))
    code_list = "\n".join(
        f"- name={json.dumps(c.name, ensure_ascii=False)}" + (f' | code_id={json.dumps(c.code_id, ensure_ascii=False)}' if c.code_id else "")
        for c in to_enrich
    )
    ctx = project_cfg.survey_context or "Open-ended survey responses."
    lang_name = project_cfg.codebook_language_name
    prompt = (
        "You are a qualitative research expert.\n\n"
        f"CODEBOOK OUTPUT LANGUAGE: {lang_name}.\n"
        f"Write all generated definitions, criteria, and example verbatims in {lang_name}.\n\n"
        f"CONTEXT:\n{ctx}\n\n"
        f"Codes without descriptions:\n{code_list}\n\n"
        f"For each code, generate in {lang_name}:\n"
        "1. A clear definition (1-2 sentences)\n2. 2-3 inclusion criteria\n3. 1-2 exclusion criteria\n4. 2 example verbatims\n\n"
        "Important constraints:\n- Return the \"name\" field exactly as provided above.\n"
        "- If a code_id is provided, also return the same \"code_id\" field.\n- Do not rename codes.\n\n"
        "Return ONLY valid JSON, with no Markdown:\n"
        '{"codes":[{"name":"<exact name>","code_id":"<id if provided>","definition":"...",'
        '"inclusion_criteria":["..."],"exclusion_criteria":["..."],"example_verbatims":["...","..."]}]}'
    )
    try:
        resp = chat_with_retry(
            client, model=project_cfg.coding_model,
            messages=[
                {"role": "system", "content": "Qualitative research expert. Return ONLY valid JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3, max_tokens=coding_cfg.codebook_generation_max_tokens,
            timeout=project_cfg.openai_timeout_seconds, max_retries=project_cfg.openai_max_retries,
            usage_log=usage_log,
        )
        enriched = json.loads(extract_json(resp.choices[0].message.content.strip()))
    except Exception as e:  # noqa: BLE001 - mirrors notebook's defensive catch-all
        logger.error("Enrichment call/parse failed: %s", e)
        enriched = {"codes": []}

    by_name = {canonical_code_key(c.get("name", "")): c for c in enriched.get("codes", []) if c.get("name")}
    by_id = {
        clean_code_id(c.get(CODE_ID_FIELD, "") or c.get("code_id", "")): c
        for c in enriched.get("codes", [])
        if clean_code_id(c.get(CODE_ID_FIELD, "") or c.get("code_id", ""))
    }

    matched = []
    for code in codebook.codes:
        if clean_optional_text(code.definition):
            continue
        ec = by_id.get(code.code_id) if code.code_id else None
        if ec is None:
            ec = by_name.get(canonical_code_key(code.name))
        if ec is None:
            continue
        definition = clean_optional_text(ec.get("definition", ""))
        if not definition:
            continue
        code.definition = definition
        code.inclusion_criteria = list(ec.get("inclusion_criteria") or code.inclusion_criteria)
        code.exclusion_criteria = list(ec.get("exclusion_criteria") or code.exclusion_criteria)
        code.example_verbatims = list(ec.get("example_verbatims") or code.example_verbatims)
        code.definition_source = code.definition_source or "ai_enrichment"
        matched.append(code.name)

    still_missing = [c.name for c in codebook.codes if not clean_optional_text(c.definition)]
    if still_missing:
        logger.warning("AI enrichment did not fill definitions for: %s", still_missing)
        if fill_missing_with_fallback:
            codebook = apply_definition_fallbacks(
                project_cfg, codebook, parent_code=fallback_parent_code, merged_from=fallback_merged_from
            )
    logger.info("Enrichment complete. Matched definitions for: %s", matched)
    return codebook
