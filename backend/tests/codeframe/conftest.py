from pathlib import Path

import pandas as pd
import pytest

from codeframe.config import ClusterConfig, CodingConfig, PreprocessConfig, ProjectConfig
from tests.fixtures.fake_openai import FakeOpenAI

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def fake_client():
    return FakeOpenAI()


@pytest.fixture
def project_cfg():
    return ProjectConfig(
        survey_context="Consumers of a beverage brand describe what they like about it.",
        source_language_code="en", target_language_code="en", codebook_language_code="en",
        random_seed=42,
    )


@pytest.fixture
def preprocess_cfg():
    return PreprocessConfig()


@pytest.fixture
def cluster_cfg():
    return ClusterConfig(random_seed=42)


@pytest.fixture
def coding_cfg():
    return CodingConfig()


@pytest.fixture
def tiny_survey_path():
    return DATA_DIR / "tiny_survey.xlsx"


@pytest.fixture
def sample_texts(tiny_survey_path):
    return pd.read_excel(tiny_survey_path)["feedback"].tolist()
