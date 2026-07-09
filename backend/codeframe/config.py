"""Pydantic configuration models for the codeframe pipeline.

Ported from notebook sections 0-B (project configuration) and 0-D (constants).
Every downstream function takes one or more of these explicitly instead of
reading module-level globals, so the pipeline is deterministic and testable.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict

LANGUAGE_NAME_BY_CODE: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "ar": "Arabic",
}

SUPPORTED_CODEBOOK_LANGUAGE_CODES = frozenset({"fr", "en"})

# Phrases treated as empty / non-codeable responses (FR + EN). Notebook 0-D.
DEFAULT_EMPTY_RESPONSES: frozenset[str] = frozenset({
    "n/a", "na", "none", "no", "yes", "idk", "dk", "dont know", "don't know",
    "nothing", "no comment", "no comments", "-", ".", "..", "...", "nil",
    "not applicable", "no answer", "no response", "blank", "skip", "skipped",
    "", "aucun", "aucune", "rien", "néant", "sans", "—",
    "d'accord", "ras", "r.a.s", "pas de commentaire", "aucun commentaire",
    "je ne sais pas", "je sais pas", "rien à signaler", "rien a signaler",
})

DEFAULT_MIN_WORDS = 2


class ProjectConfig(BaseModel):
    """Survey context, language, and model settings. Notebook 0-B."""

    survey_question: str = ""
    survey_context: str = ""

    source_language_code: str = "en"
    target_language_code: str = "fr"
    codebook_language_code: str = "fr"

    reasoning_model: str = "gpt-5.4-mini"
    coding_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    embedding_batch_size: int = 100

    openai_timeout_seconds: float = 180.0
    openai_max_retries: int = 10

    random_seed: int = 42

    def model_post_init(self, __context) -> None:
        code = str(self.codebook_language_code or "fr").lower().strip()
        if code not in SUPPORTED_CODEBOOK_LANGUAGE_CODES:
            raise ValueError(
                f'Unsupported codebook_language_code="{code}". Use "fr" or "en".'
            )
        self.codebook_language_code = code

    @property
    def text_column(self) -> str:
        """Column name produced by preprocessing/translation and used downstream."""
        return f"final_text_{self.target_language_code}"

    def language_name(self, code: str) -> str:
        return LANGUAGE_NAME_BY_CODE.get(code, code)

    @property
    def codebook_language_name(self) -> str:
        return self.language_name(self.codebook_language_code)

    @property
    def codebook_is_english(self) -> bool:
        return self.codebook_language_code == "en"


class PreprocessConfig(BaseModel):
    """Cleaning / validity thresholds. Notebook 0-D, 1-A."""

    model_config = ConfigDict(frozen=False)

    default_min_words: int = DEFAULT_MIN_WORDS
    empty_responses: frozenset[str] = DEFAULT_EMPTY_RESPONSES


class ClusterConfig(BaseModel):
    """UMAP + HDBSCAN parameters. Notebook 0-B / 2-A."""

    umap_components: int = 10
    umap_neighbors: int = 15
    min_samples: int = 1
    epsilon: float = 0.4
    representatives: int = 3
    random_seed: int = 42


class CodingConfig(BaseModel):
    """Batch sizes, token caps, and coding-output options. Notebook 0-B."""

    coding_batch_size: int = 10
    translation_batch_size: int = 10

    use_compact_codebook_for_coding: bool = True
    save_coding_reasoning: bool = False

    codebook_generation_max_tokens: int = 8000
    codebook_generation_retry_max_tokens: int = 12000
    codebook_target_codes_cap: Optional[int] = None

    other_fallback_confidence: float = 0.50
