import openpyxl

from codeframe.demo import main, run_demo
from tests.fixtures.fake_openai import FakeOpenAI


def test_run_demo_end_to_end_produces_five_sheet_workbook(tiny_survey_path, tmp_path):
    result = run_demo(
        tiny_survey_path, output_dir=tmp_path, text_column="feedback",
        client=FakeOpenAI(), seed=42,
    )

    assert result["n_rows_loaded"] == 30
    assert 3 <= len(result["codebook_codes"]) <= 6 + 1  # themes + catch-all
    wb = openpyxl.load_workbook(result["workbook_path"])
    assert len(wb.sheetnames) == 5


def test_run_demo_is_deterministic_across_repeated_runs(tiny_survey_path, tmp_path):
    result_1 = run_demo(tiny_survey_path, output_dir=tmp_path / "run1", text_column="feedback", client=FakeOpenAI(), seed=42)
    result_2 = run_demo(tiny_survey_path, output_dir=tmp_path / "run2", text_column="feedback", client=FakeOpenAI(), seed=42)

    assert result_1["cluster_labels"] == result_2["cluster_labels"]
    assert result_1["codebook_codes"] == result_2["codebook_codes"]


def test_main_cli_with_fake_llm_flag(tiny_survey_path, tmp_path, capsys):
    result = main([str(tiny_survey_path), "--fake-llm", "--output-dir", str(tmp_path), "--text-column", "feedback"])

    captured = capsys.readouterr()
    assert "Workbook" in captured.out
    assert result["n_kept"] == 30


def test_main_without_fake_llm_and_no_api_key_raises(tiny_survey_path, tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        main([str(tiny_survey_path), "--output-dir", str(tmp_path), "--text-column", "feedback"])
        raised = False
    except RuntimeError:
        raised = True
    assert raised
