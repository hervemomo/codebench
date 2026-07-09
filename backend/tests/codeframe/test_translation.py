import pandas as pd

from codeframe.config import CodingConfig, ProjectConfig
from codeframe.translation import translate_records


def test_translate_records_noop_when_source_equals_target(fake_client):
    cfg = ProjectConfig(source_language_code="en", target_language_code="en")
    coding_cfg = CodingConfig()
    df = pd.DataFrame({"cleaned_text": ["hello there friend"], "detected_lang": ["en"]})

    out = translate_records(df, cfg, coding_cfg, fake_client)

    assert out[cfg.text_column].tolist() == ["hello there friend"]


def test_translate_records_translates_only_source_language_rows(fake_client):
    cfg = ProjectConfig(source_language_code="en", target_language_code="fr")
    coding_cfg = CodingConfig(translation_batch_size=2)
    df = pd.DataFrame({
        "cleaned_text": ["great taste today", "bonjour le monde entier", "nice energy boost"],
        "detected_lang": ["en", "fr", "en"],
    })

    out = translate_records(df, cfg, coding_cfg, fake_client)

    assert out.loc[0, cfg.text_column] == "[TR] great taste today"
    assert out.loc[1, cfg.text_column] == "bonjour le monde entier"
    assert out.loc[2, cfg.text_column] == "[TR] nice energy boost"


def test_translate_records_batches_across_multiple_calls(fake_client):
    cfg = ProjectConfig(source_language_code="en", target_language_code="fr")
    coding_cfg = CodingConfig(translation_batch_size=1)
    df = pd.DataFrame({
        "cleaned_text": [f"english response number {i}" for i in range(4)],
        "detected_lang": ["en"] * 4,
    })

    out = translate_records(df, cfg, coding_cfg, fake_client)

    assert all(out[cfg.text_column].str.startswith("[TR] "))
    assert len(out) == 4


def test_translate_records_no_source_language_rows_is_noop(fake_client):
    cfg = ProjectConfig(source_language_code="en", target_language_code="fr")
    coding_cfg = CodingConfig()
    df = pd.DataFrame({"cleaned_text": ["bonjour tout le monde"], "detected_lang": ["fr"]})

    out = translate_records(df, cfg, coding_cfg, fake_client)

    assert out.loc[0, cfg.text_column] == "bonjour tout le monde"


def test_translate_records_batch_failure_falls_back_to_per_item_retry(fake_client):
    cfg = ProjectConfig(source_language_code="en", target_language_code="fr")
    coding_cfg = CodingConfig(translation_batch_size=3)
    df = pd.DataFrame({
        "cleaned_text": ["good response one BATCH_TRANSLATE_FAIL", "good response two", "good response three"],
        "detected_lang": ["en", "en", "en"],
    })

    out = translate_records(df, cfg, coding_cfg, fake_client, delay=0.01)

    assert out.loc[0, cfg.text_column] == "[TR] good response one BATCH_TRANSLATE_FAIL"
    assert out.loc[1, cfg.text_column] == "[TR] good response two"
    assert out.loc[2, cfg.text_column] == "[TR] good response three"


def test_translate_records_per_item_failure_keeps_original_text(fake_client):
    cfg = ProjectConfig(source_language_code="en", target_language_code="fr")
    coding_cfg = CodingConfig(translation_batch_size=3)
    df = pd.DataFrame({
        "cleaned_text": ["unfixable response ALWAYS_TRANSLATE_FAIL", "good response two", "good response three"],
        "detected_lang": ["en", "en", "en"],
    })

    out = translate_records(df, cfg, coding_cfg, fake_client)

    assert out.loc[0, cfg.text_column] == "unfixable response ALWAYS_TRANSLATE_FAIL"
    assert out.loc[1, cfg.text_column] == "[TR] good response two"
