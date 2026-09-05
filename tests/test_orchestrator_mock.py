import os
import pytest
from unittest.mock import patch, AsyncMock
from native_orchestrator import SwarmOrchestrator, load_agent_instructions

def test_load_agent_instructions_valid():
    """Verify load_agent_instructions loads system prompt for valid role."""
    instructions = load_agent_instructions("orchestrator")
    assert isinstance(instructions, str)
    assert len(instructions) > 50

def test_load_agent_instructions_invalid():
    """Verify load_agent_instructions raises ValueError for missing role."""
    with pytest.raises(ValueError, match="Unknown agent role"):
        load_agent_instructions("nonexistent_role_xyz")

def test_swarm_orchestrator_init():
    """Verify SwarmOrchestrator initializes default paths and state."""
    orchestrator = SwarmOrchestrator("Test task", mock_mode=True)
    assert orchestrator.task_description == "Test task"
    assert orchestrator.mock_mode is True
    assert orchestrator.approved is False
    assert orchestrator.plan_path == "implementation_plan.md"
    assert orchestrator.task_path == "task.md"
    assert orchestrator.walkthrough_path == "walkthrough.md"

def test_update_live_status(tmp_path, monkeypatch):
    """Verify _update_live_status generates valid agent_live.md markdown dashboard."""
    monkeypatch.chdir(tmp_path)
    orchestrator = SwarmOrchestrator("Test task", mock_mode=True)
    orchestrator._update_live_status("Planning", "Architect", "Phase 2: Planning")
    
    assert os.path.exists("agent_live.md")
    with open("agent_live.md", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Swarm Live Execution Monitor" in content
    assert "Test task" in content
    assert "graph TD" in content

@pytest.mark.asyncio
async def test_mock_workflow_approved(tmp_path, monkeypatch):
    """Verify simulated mock workflow completes successfully when user approves."""
    monkeypatch.chdir(tmp_path)
    orchestrator = SwarmOrchestrator("Mock Test Task", mock_mode=True)
    
    # Fast-forward asyncio.sleep
    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Auto-approve gate
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value="yes"):
            await orchestrator.execute_workflow()
            
    assert orchestrator.approved is True
    assert os.path.exists("implementation_plan.md")
    assert os.path.exists("task.md")
    assert os.path.exists("walkthrough.md")
    assert os.path.exists("mock_demo_file.txt")

@pytest.mark.asyncio
async def test_mock_workflow_rejected(tmp_path, monkeypatch):
    """Verify simulated mock workflow halts cleanly when user rejects."""
    monkeypatch.chdir(tmp_path)
    orchestrator = SwarmOrchestrator("Mock Test Task", mock_mode=True)
    
    with patch("asyncio.sleep", new_callable=AsyncMock):
        # Reject gate
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value="no"):
            await orchestrator.execute_workflow()
            
    assert orchestrator.approved is False
    assert os.path.exists("implementation_plan.md")
    assert not os.path.exists("mock_demo_file.txt")
