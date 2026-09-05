import os
import sys
import types as pytypes
from unittest.mock import MagicMock

# Add repo root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Mock google.antigravity for offline test runner if package is not locally installed
if "google.antigravity" not in sys.modules:
    try:
        import google.antigravity
    except ImportError:
        google_mod = sys.modules.get("google", pytypes.ModuleType("google"))
        antigravity_mod = pytypes.ModuleType("google.antigravity")
        hooks_mod = pytypes.ModuleType("google.antigravity.hooks")

        class Policy:
            def __init__(self, action, when=None, name=None):
                self.action = action
                self.when = when
                self.name = name

            def __repr__(self):
                return f"Policy(name={self.name}, action={self.action})"

        class PolicyFactory:
            @staticmethod
            def deny(target, when=None, name=None):
                return Policy(f"deny:{target}", when=when, name=name)

            @staticmethod
            def allow(target, when=None, name=None):
                return Policy(f"allow:{target}", when=when, name=name)

            @staticmethod
            def allow_all():
                return Policy("allow_all", name="allow_all")

            @staticmethod
            def ask_user(target, handler=None, name=None):
                return Policy(f"ask_user:{target}", when=handler, name=name)

        hooks_mod.policy = PolicyFactory()

        class TypesMock:
            class CapabilitiesConfig:
                def __init__(self, enable_subagents=False):
                    self.enable_subagents = enable_subagents

            class McpSseServer:
                def __init__(self, url=None, headers=None):
                    self.url = url
                    self.headers = headers

            class McpStdioServer:
                def __init__(self, command=None, args=None, env=None):
                    self.command = command
                    self.args = args
                    self.env = env

        antigravity_mod.Agent = MagicMock()
        antigravity_mod.LocalAgentConfig = MagicMock()
        antigravity_mod.types = TypesMock()
        antigravity_mod.hooks = hooks_mod

        sys.modules["google"] = google_mod
        sys.modules["google.antigravity"] = antigravity_mod
        sys.modules["google.antigravity.hooks"] = hooks_mod
        sys.modules["google.antigravity.types"] = TypesMock()
