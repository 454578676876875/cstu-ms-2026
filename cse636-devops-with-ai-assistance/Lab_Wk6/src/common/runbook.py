"""Small helpers for loading a runbook YAML file.

Both agents read the same file two ways: live mode just dumps the raw text
into the system prompt for Claude to read, simulation mode parses it into a
dict so the scripted brain can walk the same steps.
"""

from pathlib import Path

import yaml


def load_runbook_text(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def load_runbook_dict(path: Path) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))
