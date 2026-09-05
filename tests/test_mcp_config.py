import os
import json
import pytest
from pydantic import ValidationError
from native_orchestrator import McpServerConfig, load_mcp_servers

def test_mcp_server_config_valid_command():
    """Test valid command-based (stdio) MCP server config."""
    config = McpServerConfig(command="python", args=["server.py"], env={"KEY": "VAL"})
    assert config.command == "python"
    assert config.args == ["server.py"]
    assert config.env == {"KEY": "VAL"}
    assert config.get_url() is None

def test_mcp_server_config_valid_url():
    """Test valid URL-based (SSE) MCP server config."""
    config = McpServerConfig(url="https://mcp.supabase.com/v1", headers={"Authorization": "Bearer test-key"})
    assert config.url == "https://mcp.supabase.com/v1"
    assert config.headers["Authorization"] == "Bearer test-key"
    assert config.get_url() == "https://mcp.supabase.com/v1"

def test_mcp_server_config_url_aliases():
    """Test URL alias fields like serverUrl."""
    config = McpServerConfig.model_validate({"serverUrl": "https://mcp.example.com", "headers": {}})
    assert config.url == "https://mcp.example.com"
    assert config.get_url() == "https://mcp.example.com"

def test_mcp_server_config_invalid_missing_both():
    """Test error when neither command nor URL is provided."""
    with pytest.raises(ValidationError):
        McpServerConfig()

def test_load_mcp_servers_missing_file(tmp_path, monkeypatch):
    """Test error when mcp_config.json does not exist."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="mcp_config.json is missing"):
        load_mcp_servers()

def test_load_mcp_servers_missing_supabase(tmp_path, monkeypatch):
    """Test error when mandatory supabase server is missing."""
    monkeypatch.chdir(tmp_path)
    config_data = {
        "mcpServers": {
            "search": {"command": "node", "args": ["search.js"]}
        }
    }
    with open("mcp_config.json", "w") as f:
        json.dump(config_data, f)
        
    with pytest.raises(ValueError, match="Mandatory 'supabase' server configuration is missing"):
        load_mcp_servers()

def test_load_mcp_servers_valid_stdio(tmp_path, monkeypatch):
    """Test loading valid stdio MCP server configuration."""
    monkeypatch.chdir(tmp_path)
    config_data = {
        "mcpServers": {
            "supabase": {
                "command": "python",
                "args": ["-m", "mcp_supabase", "Authorization:Bearer test-token"],
                "env": {}
            }
        }
    }
    with open("mcp_config.json", "w") as f:
        json.dump(config_data, f)
        
    servers = load_mcp_servers()
    assert len(servers) == 1

def test_load_mcp_servers_valid_sse(tmp_path, monkeypatch):
    """Test loading valid SSE MCP server configuration."""
    monkeypatch.chdir(tmp_path)
    config_data = {
        "mcpServers": {
            "supabase": {
                "url": "https://mcp.supabase.com/v1",
                "headers": {"Authorization": "Bearer test-secret-token"}
            }
        }
    }
    with open("mcp_config.json", "w") as f:
        json.dump(config_data, f)
        
    servers = load_mcp_servers()
    assert len(servers) == 1
