import json
import os

from native_orchestrator import get_policies_for_role


def test_policies_for_orchestrator():
    """Verify orchestrator receives safety policies and command execution restrictions."""
    policies = get_policies_for_role("orchestrator")
    assert len(policies) > 0
    policy_names = [p.name for p in policies if hasattr(p, "name") and p.name]
    assert "prohibited_folders" in policy_names
    assert "token_waste_grep" in policy_names
    assert "orchestrator_deny_run_command" in policy_names


def test_policies_for_auditor():
    """Verify auditor receives strict write and execution denial policies."""
    policies = get_policies_for_role("auditor")
    policy_names = [p.name for p in policies if hasattr(p, "name") and p.name]
    assert "prohibited_folders" in policy_names
    assert "auditor_deny_run_command" in policy_names
    assert any("auditor_deny_write" in name for name in policy_names)


def test_policies_for_builder():
    """Verify builder receives safety policies while retaining write capability."""
    policies = get_policies_for_role("builder")
    policy_names = [p.name for p in policies if hasattr(p, "name") and p.name]
    assert "prohibited_folders" in policy_names
    assert "builder_deny_memory" in policy_names
    assert "orchestrator_deny_run_command" not in policy_names


def test_policies_for_librarian():
    """Verify librarian receives code write restrictions."""
    policies = get_policies_for_role("librarian")
    policy_names = [p.name for p in policies if hasattr(p, "name") and p.name]
    assert "prohibited_folders" in policy_names
    assert any("librarian_deny_code_write" in name for name in policy_names)


def test_policies_for_researcher():
    """Verify researcher receives read-only write and execution denial policies."""
    policies = get_policies_for_role("researcher")
    policy_names = [p.name for p in policies if hasattr(p, "name") and p.name]
    assert "prohibited_folders" in policy_names
    assert "researcher_deny_run_command" in policy_names
    assert any("researcher_deny_write" in name for name in policy_names)


def test_lifecycle_hooks_exist():
    """Verify the 4-stage lifecycle hooks configuration and scripts exist."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    hooks_json_path = os.path.join(repo_root, ".agents", "hooks.json")
    assert os.path.exists(hooks_json_path)
    with open(hooks_json_path, encoding="utf-8") as f:
        config = json.load(f)
    assert "safety-gate" in config
    assert "quality-gate" in config
    assert "session-lifecycle" in config

    expected_scripts = [
        "safety_gate.py",
        "bundle_pre_invocation.py",
        "bundle_quality_gate.py",
        "bundle_teardown.py",
    ]
    for script in expected_scripts:
        assert os.path.exists(os.path.join(repo_root, ".agents", "hooks", script))
