"""Pipeline checkpoint: bundle a coded dataframe + codebook + metadata and
round-trip it to disk. Ported from notebook section 0-G, minus the
notebook's module-level PIPELINE_BASELINES global and named-checkpoint
aliasing — callers own the checkpoint directory naming.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from codeframe.codebook import Codebook, load_codebook, save_codebook

_DF_FILENAME = "df.parquet"
_CODEBOOK_FILENAME = "codebook.json"
_META_FILENAME = "meta.json"


@dataclass
class PipelineState:
    df: pd.DataFrame
    codebook: Codebook
    meta: dict[str, Any] = field(default_factory=dict)


def serialize(state: PipelineState, dir_path: str | Path) -> dict[str, str]:
    """Write `state` to `dir_path` as parquet (df) + JSON (codebook, meta). Path-agnostic."""
    dir_path = Path(dir_path)
    dir_path.mkdir(parents=True, exist_ok=True)

    df_path = dir_path / _DF_FILENAME
    codebook_path = dir_path / _CODEBOOK_FILENAME
    meta_path = dir_path / _META_FILENAME

    state.df.to_parquet(df_path)
    save_codebook(state.codebook, codebook_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(state.meta, f, indent=2, ensure_ascii=False, default=str)

    return {"df": str(df_path), "codebook": str(codebook_path), "meta": str(meta_path)}


def deserialize(dir_path: str | Path) -> PipelineState:
    """Load a `PipelineState` previously written by `serialize`."""
    dir_path = Path(dir_path)
    df_path = dir_path / _DF_FILENAME
    codebook_path = dir_path / _CODEBOOK_FILENAME
    meta_path = dir_path / _META_FILENAME

    missing = [str(p) for p in (df_path, codebook_path, meta_path) if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Incomplete pipeline state at {dir_path}. Missing: {missing}")

    df = pd.read_parquet(df_path)
    codebook = load_codebook(codebook_path)
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    return PipelineState(df=df, codebook=codebook, meta=meta)
