import os
import pytest

EXPECTED_AGENTS = [
    "orchestrator.txt",
    "builder.txt",
    "auditor.txt",
    "sre.txt",
    "librarian.txt",
]

def test_agents_directory_exists():
    """Verify the agents directory exists."""
    agents_dir = os.path.join(os.path.dirname(__file__), "..", "agents")
    assert os.path.exists(agents_dir)
    assert os.path.isdir(agents_dir)

@pytest.mark.parametrize("agent_file", EXPECTED_AGENTS)
def test_agent_prompt_file_validity(agent_file):
    """Verify that each agent prompt file exists, is non-empty, and contains instructions."""
    agents_dir = os.path.join(os.path.dirname(__file__), "..", "agents")
    file_path = os.path.join(agents_dir, agent_file)
    assert os.path.exists(file_path), f"Missing expected agent playbook: {agent_file}"
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
        
    assert len(content) > 50, f"Agent prompt {agent_file} is suspiciously short"
    assert "role" in content.lower() or "you are" in content.lower() or "mission" in content.lower()
