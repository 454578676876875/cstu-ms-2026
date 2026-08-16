import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ai_review


def test_get_reviewed_files_excludes_conftest():
    app_dir = Path(__file__).resolve().parents[1] / "src" / "sample_app"
    files = ai_review.get_reviewed_files(str(app_dir))
    names = [Path(f).name for f in files]
    assert "conftest.py" not in names
    assert "app.py" in names


def test_simulated_review_flags_missing_bounds_check():
    content = ai_review.read_file(
        str(Path(__file__).resolve().parents[1] / "src" / "sample_app" / "app.py")
    )
    review = ai_review.simulated_review("app.py", content)
    assert "bound validation" in review.lower()


def test_simulated_review_used_when_no_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = ai_review.review_code("x.py", "def f():\n    return 1\n")
    assert "Simulated review" in result


def test_static_findings_flags_missing_docstring():
    findings = ai_review._static_findings("def f():\n    return 1\n")
    assert any("no docstring" in f for f in findings)


def test_static_findings_no_findings_for_documented_empty_file():
    findings = ai_review._static_findings("")
    assert findings == []


def test_static_findings_handles_syntax_error_without_raising():
    findings = ai_review._static_findings("def f(:\n    pass\n")
    assert any("syntax error" in f.lower() for f in findings)


def test_static_findings_checks_async_functions_too():
    findings = ai_review._static_findings("async def f():\n    return 1\n")
    assert any("`f` has no docstring" in f for f in findings)
