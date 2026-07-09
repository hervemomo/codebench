import pandas as pd
import pytest

from codeframe.codebook import Codebook
from codeframe.state import PipelineState, deserialize, serialize


def test_serialize_deserialize_round_trip_is_lossless(tmp_path):
    df = pd.DataFrame({
        "response_id": [1, 2, 3],
        "final_text_en": ["a great response", "another one here", "a third response"],
        "code_Code A": [1, 0, 1],
    })
    codebook = Codebook.from_dict({"codes": [
        {"name": "Code A", "definition": "def a", "inclusion_criteria": ["x"], "example_verbatims": ["ex"]},
    ]})
    state = PipelineState(df=df, codebook=codebook, meta={"section": "s2", "n_rows": 3})

    serialize(state, tmp_path)
    restored = deserialize(tmp_path)

    pd.testing.assert_frame_equal(restored.df, df)
    assert restored.codebook.to_dict() == codebook.to_dict()
    assert restored.meta == {"section": "s2", "n_rows": 3}


def test_deserialize_missing_directory_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        deserialize(tmp_path / "does_not_exist")


def test_serialize_is_path_agnostic(tmp_path):
    df = pd.DataFrame({"a": [1, 2]})
    codebook = Codebook.from_dict({"codes": [{"name": "X"}]})
    state = PipelineState(df=df, codebook=codebook, meta={})

    dir_a = tmp_path / "checkpoint_a"
    dir_b = tmp_path / "nested" / "checkpoint_b"

    paths_a = serialize(state, dir_a)
    paths_b = serialize(state, dir_b)

    assert deserialize(dir_a).df.equals(deserialize(dir_b).df)
    assert paths_a["df"] != paths_b["df"]
