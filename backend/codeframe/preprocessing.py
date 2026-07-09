"""Load, clean, validate, and de-duplicate survey responses.

Ported from notebook sections 1-A/1-B. No file writes: invalid and duplicate
rows are returned as frames for the caller to persist/report as it sees fit.
"""

from __future__ import annotations

import html
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import ftfy
import pandas as pd
from lingua import Language, LanguageDetectorBuilder

from codeframe.config import PreprocessConfig

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"\bhttps?://[^\s<>]+|\bwww\.[^\s<>]+", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[\w.\-+]+@[\w.\-]+\.\w+\b", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_EMOJI_RE = re.compile(
    r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF"
    r"\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF"
    r"\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
    r"\U00002702-\U000027B0\U000024C2-\U0001F251\U0001F1E6-\U0001F1FF"
    r"\U00002600-\U000026FF]|️|\U0001F3FB|\U0001F3FC|\U0001F3FD"
    r"|\U0001F3FE|\U0001F3FF",
    re.UNICODE,
)

_LINGUA_LANGUAGES = [
    Language.ENGLISH, Language.FRENCH, Language.SPANISH, Language.GERMAN,
    Language.ITALIAN, Language.PORTUGUESE, Language.DUTCH, Language.ARABIC,
]

_lingua_detector = None


def _get_lingua_detector():
    global _lingua_detector
    if _lingua_detector is None:
        _lingua_detector = LanguageDetectorBuilder.from_languages(*_LINGUA_LANGUAGES).build()
    return _lingua_detector


def detect_language(text: str) -> str:
    """Detect language with Lingua; returns a lowercase ISO-639-1 code, or 'other'."""
    if not text or not str(text).strip():
        return "other"
    lang = _get_lingua_detector().detect_language_of(str(text))
    if lang is None:
        return "other"
    return lang.iso_code_639_1.name.lower()


def load_survey_data(
    filepath: str | Path, text_column: str, sheet_name: int | str = 0, id_column: Optional[str] = None
) -> pd.DataFrame:
    """Load survey responses from Excel or CSV. Drops blank rows."""
    path = Path(filepath)
    df = pd.read_excel(path, sheet_name=sheet_name) if path.suffix.lower() in (".xlsx", ".xls") else pd.read_csv(path)
    if text_column not in df.columns:
        raise ValueError(f"Column '{text_column}' not found. Available: {list(df.columns)}")
    initial = len(df)
    df = df[df[text_column].notna() & df[text_column].astype(str).str.strip().ne("")].copy()
    df["response_id"] = df[id_column] if id_column and id_column in df.columns else range(1, len(df) + 1)
    df["original_text"] = df[text_column].astype(str)
    logger.info("Loaded %s responses (%s blank rows removed)", len(df), initial - len(df))
    return df


def clean_text(
    text,
    *,
    normalize_form: str = "NFC",
    remove_control_chars: bool = True,
    fix_entities: bool = True,
    replace_urls_with: str = "__URL__",
    replace_emails_with: str = "__EMAIL__",
    emoji_handling: str = "remove",
    emoji_token: str = "__EMOJI__",
    lowercase: bool = False,
    strip_accents: bool = False,
) -> str:
    """Sanitise a response string: HTML, encoding, URLs, emails, emoji, whitespace."""
    try:
        if pd.isna(text):
            return ""
    except (TypeError, ValueError):
        pass
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)

    text = html.unescape(text)
    text = ftfy.fix_text(text, normalization=normalize_form, remove_control_chars=remove_control_chars, fix_entities=fix_entities)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _URL_RE.sub(f" {replace_urls_with} " if replace_urls_with else " ", text)
    text = _EMAIL_RE.sub(f" {replace_emails_with} " if replace_emails_with else " ", text)
    if emoji_handling == "token":
        text = _EMOJI_RE.sub(f" {emoji_token} ", text)
    elif emoji_handling == "remove":
        text = _EMOJI_RE.sub(" ", text)
    if lowercase:
        text = text.lower()
    if strip_accents:
        text = "".join(c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip()


def is_valid_response(text: str, cfg: PreprocessConfig) -> bool:
    """Return True only if the response is substantive enough to code."""
    if not text:
        return False
    t = text.strip()
    if not t or t.lower() in cfg.empty_responses:
        return False
    if re.fullmatch(r"[\W_]+", t):
        return False
    if t.lower() in {"__url__", "__email__", "__emoji__"}:
        return False
    return len(t.split()) >= cfg.default_min_words


@dataclass
class PreprocessResult:
    kept: pd.DataFrame
    invalid: pd.DataFrame
    duplicates: pd.DataFrame


def preprocess(df: pd.DataFrame, cfg: PreprocessConfig, text_column: str = "original_text") -> PreprocessResult:
    """Clean, validate, de-duplicate, and detect language. No file writes.

    `invalid` and `duplicates` may overlap (an invalid row can also be a
    duplicate) — this mirrors the notebook's audit-trail semantics. `kept`
    excludes both invalid and duplicate rows.
    """
    logger.info("Starting preprocessing...")
    df = df.copy()
    df["cleaned_text"] = df[text_column].apply(clean_text)
    df["is_valid"] = df["cleaned_text"].apply(lambda x: is_valid_response(x, cfg))
    df["is_duplicate"] = df.duplicated(subset=["cleaned_text"], keep="first")

    invalid = df[~df["is_valid"]].copy()
    duplicates = df[df["is_duplicate"]].copy()

    kept = df[df["is_valid"] & ~df["is_duplicate"]].copy()
    kept = kept.drop(columns=["is_valid", "is_duplicate"])
    kept["detected_lang"] = kept["cleaned_text"].apply(detect_language)

    logger.info("Removed %s records. %s remaining.", len(df) - len(kept), len(kept))
    return PreprocessResult(kept=kept, invalid=invalid, duplicates=duplicates)
