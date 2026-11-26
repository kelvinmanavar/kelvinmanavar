"""Checks on workflow files and automation docs (Requirements 10.1, 10.2, 10.3, 10.6, 10.7, 12.9, 14.8)."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _load(name):
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8"))


def _triggers(wf):
    # YAML 1.1 parses the bare key `on` as boolean True.
    return wf["on"] if "on" in wf else wf[True]


def test_update_workflow_triggers():
    on = _triggers(_load("update-profile.yml"))
    assert on["schedule"][0]["cron"]
    assert "workflow_dispatch" in on
    assert "profile_gen/**" in on["push"]["paths"]
    assert "profile.config.json" in on["push"]["paths"]


def test_update_workflow_permissions_and_concurrency():
    wf = _load("update-profile.yml")
    assert wf["permissions"]["contents"] == "write"
    assert wf["concurrency"]["group"]
    assert wf["concurrency"]["cancel-in-progress"] is False


def test_test_workflow_read_only_permissions():
    assert _load("test.yml")["permissions"]["contents"] == "read"


def test_automation_doc_headings():
    text = (ROOT / "docs" / "PROFILE_AUTOMATION.md").read_text(encoding="utf-8")
    headings = [l.lstrip("#").strip().lower() for l in text.splitlines() if l.startswith("#")]
    for required in ("section markers", "configuration", "running locally", "profile_stats_token"):
        assert any(required in h for h in headings), required
