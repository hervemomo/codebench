import pandas as pd

from codeframe.preprocessing import clean_text, is_valid_response, load_survey_data, preprocess


def test_load_survey_data_drops_blank_rows(tmp_path):
    df = pd.DataFrame({"feedback": ["good response here", "", None, "another good response"]})
    path = tmp_path / "survey.xlsx"
    df.to_excel(path, index=False)

    loaded = load_survey_data(path, "feedback")

    assert len(loaded) == 2
    assert "response_id" in loaded.columns
    assert "original_text" in loaded.columns
    assert list(loaded["response_id"]) == [1, 2]


def test_load_survey_data_missing_column_raises(tmp_path):
    df = pd.DataFrame({"other": ["a"]})
    path = tmp_path / "survey.xlsx"
    df.to_excel(path, index=False)

    try:
        load_survey_data(path, "feedback")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_preprocess_drops_empty_responses(preprocess_cfg):
    df = pd.DataFrame({"original_text": ["n/a", "good product overall", "aucun", "great taste today"]})

    result = preprocess(df, preprocess_cfg)

    assert len(result.kept) == 2
    assert len(result.invalid) == 2
    assert set(result.kept["original_text"]) == {"good product overall", "great taste today"}


def test_preprocess_min_word_filter(preprocess_cfg):
    df = pd.DataFrame({"original_text": ["good", "this is long enough response"]})

    result = preprocess(df, preprocess_cfg)

    assert len(result.kept) == 1
    assert result.kept.iloc[0]["original_text"] == "this is long enough response"
    assert len(result.invalid) == 1


def test_preprocess_duplicate_detection(preprocess_cfg):
    df = pd.DataFrame({
        "original_text": ["great tasting drink here", "great tasting drink here", "totally different comment here"],
    })

    result = preprocess(df, preprocess_cfg)

    assert len(result.kept) == 2
    assert len(result.duplicates) == 1
    assert result.duplicates.iloc[0]["original_text"] == "great tasting drink here"


def test_preprocess_invalid_and_duplicate_can_overlap(preprocess_cfg):
    df = pd.DataFrame({"original_text": ["n/a", "n/a", "valid enough response"]})

    result = preprocess(df, preprocess_cfg)

    # Both "n/a" rows are invalid; the second is also flagged duplicate.
    assert len(result.invalid) == 2
    assert len(result.duplicates) == 1
    assert len(result.kept) == 1


def test_preprocess_adds_detected_lang_to_kept_only(preprocess_cfg):
    df = pd.DataFrame({"original_text": ["this is a great tasting drink overall"]})

    result = preprocess(df, preprocess_cfg)

    assert "detected_lang" in result.kept.columns
    assert "detected_lang" not in result.invalid.columns


def test_clean_text_strips_html_urls_and_emails():
    text = clean_text("<b>Hello</b> visit https://example.com or mail me@example.com now!!")

    assert "<b>" not in text
    assert "__URL__" in text
    assert "__EMAIL__" in text


def test_clean_text_handles_none_and_nan():
    assert clean_text(None) == ""
    assert clean_text(float("nan")) == ""


def test_is_valid_response_respects_min_words(preprocess_cfg):
    assert not is_valid_response("no", preprocess_cfg)
    assert not is_valid_response("", preprocess_cfg)
    assert not is_valid_response("!!!", preprocess_cfg)
    assert is_valid_response("this response works well", preprocess_cfg)


def test_is_valid_response_respects_empty_responses_set(preprocess_cfg):
    assert not is_valid_response("n/a", preprocess_cfg)
    assert not is_valid_response("N/A", preprocess_cfg)
