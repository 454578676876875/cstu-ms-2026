import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "assignment"))

import remediation_agent as ra


def test_f401_pattern_parses_flake8_output_line():
    line = "C:\\repo\\app\\inventory_ops.py:2:1: F401 'os' imported but unused"
    m = ra.F401_PATTERN.match(line)
    assert m is not None
    assert m.group("module") == "os"
    assert m.group("line") == "2"


def test_propose_fix_removes_exactly_the_flagged_line(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("import json\nimport os\n\n\ndef f():\n    return json.dumps({})\n")
    removed, fixed = ra.propose_fix(f, 2)
    assert removed.strip() == "import os"
    assert "import os" not in fixed
    assert "import json" in fixed
    assert "def f():" in fixed


def test_find_unused_imports_detects_a_real_violation(tmp_path, monkeypatch):
    (tmp_path / "bad.py").write_text("import os\n\n\ndef f():\n    return 1\n")
    monkeypatch.setattr(ra, "APP_DIR", tmp_path)
    findings = ra.find_unused_imports()
    modules = [module for _, _, module in findings]
    assert "os" in modules


def test_inventory_ops_is_clean_after_the_captured_remediation_run():
    """app/inventory_ops.py's unused `import os` was removed by the approved run captured in
    transcripts/assignment_remediation_approved.txt. Confirm it stays clean."""
    findings = ra.find_unused_imports()
    assert findings == []
