"""CLI: run the whole codeframe pipeline end-to-end against one survey file.

Usage:
    python -m codeframe.demo <survey.xlsx> --fake-llm
    python -m codeframe.demo <survey.xlsx> --text-column feedback

With --fake-llm, a deterministic fake OpenAI client from tests/fixtures is
used so the pipeline runs with zero external API calls.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from codeframe import clustering, coding, preprocessing, reporting, translation
from codeframe.codebook import generate_codebook
from codeframe.config import ClusterConfig, CodingConfig, PreprocessConfig, ProjectConfig
from codeframe.llm import LLMClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)


def _build_client(fake_llm: bool, project_cfg: ProjectConfig) -> LLMClient:
    if fake_llm:
        from tests.fixtures.fake_openai import FakeOpenAI

        return FakeOpenAI()

    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Pass --fake-llm to run without a real API key.")
    return OpenAI(api_key=api_key, max_retries=0, timeout=project_cfg.openai_timeout_seconds)


def run_demo(
    survey_path: str | Path,
    *,
    output_dir: str | Path = "/tmp/out",
    text_column: str = "feedback",
    sheet: int | str = 0,
    seed: int = 42,
    fake_llm: bool = False,
    client: Optional[LLMClient] = None,
    survey_context: str = "Open-ended survey responses.",
    target_language_code: str = "en",
    source_language_code: str = "en",
) -> dict[str, Any]:
    """Run load -> preprocess -> translate -> cluster -> codebook -> code -> report.

    Returns a summary dict including `cluster_labels`, which is identical
    across repeated runs against the same input given the same `seed`.
    """
    output_dir = Path(output_dir)

    project_cfg = ProjectConfig(
        survey_context=survey_context, random_seed=seed,
        source_language_code=source_language_code, target_language_code=target_language_code,
        codebook_language_code="en" if target_language_code == "en" else "fr",
    )
    preprocess_cfg = PreprocessConfig()
    cluster_cfg = ClusterConfig(random_seed=seed)
    coding_cfg = CodingConfig()

    client = client or _build_client(fake_llm, project_cfg)

    df_raw = preprocessing.load_survey_data(survey_path, text_column, sheet_name=sheet)
    logger.info("Rows loaded: %s", len(df_raw))

    result = preprocessing.preprocess(df_raw, preprocess_cfg)
    logger.info("Kept: %s  Invalid: %s  Duplicates: %s", len(result.kept), len(result.invalid), len(result.duplicates))

    translated = translation.translate_records(result.kept, project_cfg, coding_cfg, client)

    texts = translated[project_cfg.text_column].tolist()
    embeddings = clustering.embed(texts, project_cfg, client)
    cluster_result = clustering.discover_themes(embeddings, texts, cluster_cfg)
    logger.info("Clusters discovered: %s", len(cluster_result.representatives))

    codebook_obj = generate_codebook(
        client, cluster_result.representatives, project_cfg, coding_cfg,
        target_codes=len(cluster_result.representatives),
    )
    logger.info("Codes generated: %s -> %s", len(codebook_obj.codes), [c.name for c in codebook_obj.codes])

    def _progress(batch_i: int, n_batches: int) -> None:
        logger.info("Coding batch %s/%s", batch_i, n_batches)

    coded_df = coding.apply_codes(translated, codebook_obj, project_cfg, coding_cfg, client, progress_cb=_progress)
    coded_df = coding.add_codes_column(coded_df, codebook_obj)

    workbook_path = reporting.export_workbook(coded_df, codebook_obj, output_dir / "demo_report.xlsx", text_column=project_cfg.text_column)
    charts = reporting.export_charts(coded_df, codebook_obj, output_dir, file_stem="demo")
    logger.info("Workbook written -> %s", workbook_path)

    return {
        "n_rows_loaded": len(df_raw),
        "n_kept": len(result.kept),
        "n_invalid": len(result.invalid),
        "n_duplicates": len(result.duplicates),
        "codebook_codes": [c.name for c in codebook_obj.codes],
        "cluster_labels": cluster_result.labels.tolist(),
        "workbook_path": workbook_path,
        "charts": charts,
    }


def main(argv: Optional[list[str]] = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description="Run the codeframe pipeline end-to-end against one survey file.")
    parser.add_argument("survey_path", help="Path to an .xlsx/.xls/.csv survey file.")
    parser.add_argument("--fake-llm", action="store_true", help="Use the deterministic fake OpenAI client (no network calls).")
    parser.add_argument("--output-dir", default="/tmp/out")
    parser.add_argument("--text-column", default="feedback")
    parser.add_argument("--sheet", default=0)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    result = run_demo(
        args.survey_path, output_dir=args.output_dir, text_column=args.text_column,
        sheet=args.sheet, seed=args.seed, fake_llm=args.fake_llm,
    )
    print(f"Rows loaded    : {result['n_rows_loaded']}")
    print(f"Kept / Invalid / Duplicates : {result['n_kept']} / {result['n_invalid']} / {result['n_duplicates']}")
    print(f"Codes generated: {len(result['codebook_codes'])} -> {result['codebook_codes']}")
    print(f"Workbook       : {result['workbook_path']}")
    return result


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
