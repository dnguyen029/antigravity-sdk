"""
================================================================================
🏛️ NATIVE ANTIGRAVITY 2.0 SDK ORCHESTRATION BLUEPRINT
================================================================================

This module implements the execution and governance engine for the Antigravity
Swarm using the native google-antigravity SDK. It coordinates lifecycle states,
enforces permission boundaries via hooks, and leverages workspace capabilities.
"""

import os
import sys
import json
import logging
import asyncio
from google.antigravity import Agent, LocalAgentConfig, types
from google.antigravity.hooks import policy
from pydantic import BaseModel, Field, model_validator, AliasChoices
from typing import Optional, Dict, List
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("native_orchestrator")

# Load environment variables
load_dotenv()

# ==========================================
# 📋 PYDANTIC SCHEMAS FOR CONFIGURATION
# ==========================================
class McpServerConfig(BaseModel):
    command: Optional[str] = None
    args: List[str] = Field(default_factory=list)
    env: Dict[str, str] = Field(default_factory=dict)
    
    url: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("url", "serverUrl", "serverURL")
    )
    headers: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_server_type(self) -> "McpServerConfig":
        has_remote = self.url is not None
        has_command = self.command is not None
        
        if not has_remote and not has_command:
            raise ValueError("An MCP server configuration must have either a 'command' or a remote URL.")
        return self
        
    def get_url(self) -> Optional[str]:
        return self.url

def load_mcp_servers(agent_role: str | None = None):
    """Load and parse workspace MCP servers."""
    mcp_servers = []
    config_path = "mcp_config.json"
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"{config_path} is missing. Cannot verify MCP configurations.")
    
    with open(config_path, "r") as f:
        config = json.load(f)
    
    servers = config.get("mcpServers", {})
    
    # Enforce mandatory Supabase registry connection to protect the database layer
    if "supabase" not in servers:
        raise ValueError("Mandatory 'supabase' server configuration is missing from mcp_config.json.")
        
    for name, srv_dict in servers.items():
        try:
            srv = McpServerConfig(**srv_dict)
        except Exception as e:
            raise ValueError(f"Invalid MCP configuration for server '{name}': {e}")
            
        url = srv.get_url()
        if url:
            headers = srv.headers
            env_vars = srv.env
            
            # Map API keys from env to Authorization headers if not already set
            if "Authorization" not in headers:
                token_val = None
                for k, v in env_vars.items():
                    if "API_KEY" in k or "TOKEN" in k or k == "SUPABASE_ACCESS_TOKEN":
                        token_val = v
                        break
                if not token_val:
                    for k in ["SUPABASE_ACCESS_TOKEN", "EXA_API_KEY", "GEMINI_API_KEY"]:
                        if k in os.environ:
                            token_val = os.environ[k]
                            break
                if token_val:
                    headers["Authorization"] = f"Bearer {token_val}"
                        
            if "supabase" in name or "supabase.com" in url:
                if "Authorization" not in headers or not headers.get("Authorization"):
                    raise ValueError(f"Mandatory '{name}' (Supabase) is missing a valid Authorization header.")
                    
            mcp_servers.append(types.McpSseServer(url=url, headers=headers))
        else:
            command = srv.command
            args = srv.args
            env = srv.env
            
            # Security audit: Verify authorization headers for supabase if it runs via stdio wrappers
            if name == "supabase":
                args_str = " ".join(args)
                if "Authorization:Bearer" not in args_str and "Authorization" not in args_str:
                    raise ValueError("Mandatory 'supabase' server is missing a valid Authorization header in its arguments.")
            
            mcp_servers.append(types.McpStdioServer(
                command=command,
                args=args,
                env=env
            ))
    return mcp_servers

def get_policies_for_role(agent_role: str):
    """Native SDK Safety Hook & Quartet Policy Guard.
    Validates execution boundaries and directory protections dynamically using native Policy objects.
    """
    role_lower = agent_role.lower()
    
    # 1. Prohibited Directories (Access Protection)
    prohibited_folders = [".venv", ".git", "venv", "node_modules"]
    
    def contains_prohibited_folder(args):
        paths_to_check = [
            args.get(k) for k in ["path", "AbsolutePath", "DirectoryPath", "TargetFile", "SearchPath"]
            if k in args and isinstance(args[k], str)
        ]
        for file_path in paths_to_check:
            normalized_path = file_path.replace("\\", "/")
            parts = normalized_path.split("/")
            if any(folder in parts for folder in prohibited_folders):
                return True
        return False

    # 2. Token-Waste Prevention
    def is_broad_grep_search(args):
        path_arg = args.get("SearchPath") or ""
        query_arg = args.get("Query") or ""
        current_dir = os.getcwd()
        if path_arg in ["/", current_dir, current_dir + "/"]:
            if query_arg in ["", "*", ".*"] or len(query_arg) < 2:
                return True
        return False

    def is_broad_list_directory(args):
        path_arg = args.get("DirectoryPath") or args.get("path") or args.get("SearchDirectory") or ""
        user_home = os.path.expanduser("~")
        if path_arg in ["/", "/home", user_home, user_home + "/"]:
            return True
        return False

    # 3. Write Constraints & Document Debt Prevention
    def is_writing_without_plan(args):
        target_file = args.get("TargetFile") or args.get("file_path") or args.get("path") or ""
        target_basename = os.path.basename(target_file)
        if target_basename in ["implementation_plan.md", "task.md", "walkthrough.md"]:
            return False
        plan_file = "implementation_plan.md"
        if not os.path.exists(plan_file):
            return True
        try:
            with open(plan_file, "r", encoding="utf-8") as f:
                content = f.read().lower()
            # Flexibly check for presence of RCA / plan elements
            has_rca = "root cause" in content or "rca" in content
            has_proposed = "proposed changes" in content or "proposed" in content or "plan" in content
            if has_rca or has_proposed:
                return False
        except Exception:
            return True
        return True

    policies = [
        policy.deny("*", when=contains_prohibited_folder, name="prohibited_folders"),
        policy.deny("grep_search", when=is_broad_grep_search, name="token_waste_grep"),
        policy.deny("list_dir", when=is_broad_list_directory, name="token_waste_list_dir"),
        policy.deny("find_by_name", when=is_broad_list_directory, name="token_waste_find_by_name"),
    ]

    write_tools = ["write_file", "edit_file", "write_to_file", "replace_file_content", "multi_replace_file_content", "delete_file"]
    for wt in write_tools:
        policies.append(policy.deny(wt, when=is_writing_without_plan, name=f"write_guard_{wt}"))

    # 4. Role-Based Quartet Permission Check
    if "orchestrator" in role_lower or "architect" in role_lower:
        def is_not_planning_file(args):
            target_file = args.get("TargetFile") or args.get("file_path") or args.get("path") or ""
            return os.path.basename(target_file) not in ["implementation_plan.md", "task.md", "walkthrough.md"]
            
        for wt in write_tools:
            policies.append(policy.deny(wt, when=is_not_planning_file, name=f"orchestrator_write_restrict_{wt}"))
        policies.append(policy.deny("run_command", name="orchestrator_deny_run_command"))
        policies.append(policy.deny("execute_command", name="orchestrator_deny_exec_command"))

    elif "auditor" in role_lower:
        for wt in write_tools:
            policies.append(policy.deny(wt, name=f"auditor_deny_write_{wt}"))
        policies.append(policy.deny("run_command", name="auditor_deny_run_command"))
        policies.append(policy.deny("execute_command", name="auditor_deny_exec_command"))

    elif "librarian" in role_lower or "writer" in role_lower:
        def is_code_config_file(args):
            target_file = args.get("TargetFile") or args.get("file_path") or args.get("path") or ""
            _, ext = os.path.splitext(os.path.basename(target_file))
            return ext.lower() in [".py", ".json", ".env", ".yaml", ".yml"]
            
        for wt in write_tools:
            policies.append(policy.deny(wt, when=is_code_config_file, name=f"librarian_deny_code_write_{wt}"))

    elif "builder" in role_lower or "developer" in role_lower or "admin" in role_lower or "sre" in role_lower:
        policies.append(policy.deny("memory", name="builder_deny_memory"))
        policies.append(policy.deny("apply_migration", name="builder_deny_migration"))
        
        def is_modifying_sql(args):
            query = args.get("query", "").strip().upper()
            write_keywords = ["INSERT ", "UPDATE ", "DELETE ", "DROP ", "CREATE ", "ALTER ", "REPLACE ", "TRUNCATE "]
            return any(kw in query for kw in write_keywords)
            
        policies.append(policy.deny("execute_sql", when=is_modifying_sql, name="builder_deny_write_sql"))

    # Approval handler for run_command / execute_command in dynamic/interactive/developer scenarios
    async def ask_user_handler(tool_call):
        print(f"\n❓ [APPROVAL REQUIRED] Agent '{agent_role}' wants to run: {tool_call.name}")
        if hasattr(tool_call, "arguments") and tool_call.arguments:
            print(f"Arguments: {json.dumps(tool_call.arguments, indent=2)}")
        user_input = await asyncio.to_thread(input, "Allow execution? (yes/no): ")
        return user_input.strip().lower() in ["yes", "y"]

    policies.append(policy.ask_user("run_command", handler=ask_user_handler, name="ask_run_command"))
    policies.append(policy.ask_user("execute_command", handler=ask_user_handler, name="ask_exec_command"))
    policies.append(policy.allow_all())
    
    return policies

# Extend LocalAgentConfig with load_from_workspace class method
def load_from_workspace(cls, agent_role: str, **kwargs):
    """
    Class method to load workspace settings for a specific agent role,
    inheriting MCP configurations, workspaces, and safety policies.
    """
    mcp_servers = load_mcp_servers(agent_role)
    policies = get_policies_for_role(agent_role)
    
    # Restrict to workspace directories
    workspace_path = os.getcwd()
    workspaces = [workspace_path]
    
    config_args = {
        "mcp_servers": mcp_servers,
        "policies": policies,
        "workspaces": workspaces,
    }
    # Update with any explicit overrides/args provided by caller
    config_args.update(kwargs)
    return cls(**config_args)

LocalAgentConfig.load_from_workspace = classmethod(load_from_workspace)  # type: ignore

def load_agent_instructions(role: str) -> str:
    """Load system instructions for an agent role, dynamically mapping aliases."""
    role_map = {
        "architect": "orchestrator.txt",
        "orchestrator": "orchestrator.txt",
        "builder": "builder.txt",
        "developer": "builder.txt",
        "librarian": "librarian.txt",
        "writer": "librarian.txt",
        "sre": "sre.txt",
        "admin": "sre.txt",
        "auditor": "auditor.txt",
        "receptionist": "receptionist.txt"
    }
    filename = role_map.get(role.lower())
    if not filename:
        raise ValueError(f"Unknown agent role: {role}")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, "agents", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

class SwarmOrchestrator:
    def __init__(self, task_description: str):
        self.task_description = task_description
        self.plan_path = "implementation_plan.md"
        self.task_path = "task.md"
        self.walkthrough_path = "walkthrough.md"
        self.approved = False
        self.memory_context = ""

    def _update_live_status(self, phase: str, active_agent: str, status_msg: str):
        """Helper to update agent_live.md with the current task phase and a Mermaid diagram."""
        live_path = "agent_live.md"
        
        mermaid_lines = []
        mermaid_lines.append("graph TD")
        mermaid_lines.append("    Discovery(🔍 Discovery) --> Planning(📋 Planning)")
        mermaid_lines.append("    Planning --> Correction{🔄 Self-Correction}")
        mermaid_lines.append("    Correction -->|Flawed Plan| Planning")
        mermaid_lines.append("    Correction -->|Valid Plan| Approval(🛑 Approval Gate)")
        mermaid_lines.append("    Approval --> Execution(💻 Execution)")
        mermaid_lines.append("    Execution --> Verification(🛡️ Verification)")
        mermaid_lines.append("    Verification --> Escalation{🛑 Escalation Gate}")
        mermaid_lines.append("    Escalation -->|Failed| Rollback(⚠️ Rollback)")
        mermaid_lines.append("    Escalation -->|Passed| Success(🎉 Success)")
        
        if phase:
            mermaid_lines.append(f"    style {phase} fill:#ff9900,stroke:#333,stroke-width:4px,color:#000")
            
        content = f"""# 🛰️ Swarm Live Execution Monitor

This dashboard displays the active execution phase and handoff flows of the Antigravity Swarm.

---

## ⚡ Active Task
*   **Task**: {self.task_description}
*   **Active Agent**: {active_agent}
*   **Current Phase**: {status_msg}

---

## 📊 Live Flow Monitor

```mermaid
{os.linesep.join(mermaid_lines)}
```
"""
        try:
            with open(live_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.warning(f"Failed to write swarm status update: {e}")

    async def execute_workflow(self):
        """Standardized async agent runner executing Discovery, Planning, and Verification stages."""
        logger.info("🔍 [PHASE 1: DISCOVERY] Initializing native workspace validation...")
        self._update_live_status("Discovery", "Librarian", "🔍 Phase 1: Discovery (Querying memory)")
        if not os.path.exists(".env"):
            raise FileNotFoundError("Missing environment credentials (.env file).")
            
        logger.info("📋 [PHASE 2: PLANNING] Querying Supermemory & Supabase database contexts...")
        try:
            librarian_instr = load_agent_instructions("librarian")
            lib_config = LocalAgentConfig.load_from_workspace(  # type: ignore
                agent_role="librarian",
                system_instructions=librarian_instr,
                capabilities=types.CapabilitiesConfig(enable_subagents=True),
                max_turns=5
            )
            
            async with Agent(lib_config) as librarian:
                task_resp = await librarian.chat(
                    f"Search your databases for past resolutions/lessons about: \"{self.task_description}\"."
                )
                task_text = await task_resp.text()
                
                gen_resp = await librarian.chat(
                    "Search databases for general project architecture and swarm roles guidelines."
                )
                gen_text = await gen_resp.text()
                
                self.memory_context = f"=== TASK WISDOM ===\n{task_text}\n\n=== GENERAL GUIDELINES ===\n{gen_text}"
        except FileNotFoundError:
            logger.warning("Librarian instructions file missing. Skipping memory query.")

        # Planning phase with Self-Correction loop
        logger.info("Writing implementation plan using Architect agent...")
        self._update_live_status("Planning", "Architect", "📋 Phase 2: Planning (Drafting implementation plan)")
        
        for attempt in range(1, 4):
            arch_instr = load_agent_instructions("orchestrator")
            if self.memory_context:
                arch_instr += f"\n\n## 🧠 RECALLED MISSION WISDOM\n{self.memory_context}"

            arch_config = LocalAgentConfig.load_from_workspace(  # type: ignore
                agent_role="architect",
                system_instructions=arch_instr,
                capabilities=types.CapabilitiesConfig(enable_subagents=True),
                max_turns=5
            )
            async with Agent(arch_config) as architect:
                resp = await architect.chat(
                    f"Draft an implementation plan and task lists for task: \"{self.task_description}\"."
                )
                plan_content = await resp.text()
                
            self._update_live_status("Correction", "Orchestrator", f"🔄 Self-Correction Loop (Attempt {attempt}/3: Validating plan)")
            
            # Constraint Simulation Checks
            content_lower = plan_content.lower()
            has_rca = "root cause" in content_lower or "rca" in content_lower
            has_proposed = "proposed changes" in content_lower or "proposed" in content_lower or "plan" in content_lower
            has_verification = "verification plan" in content_lower or "verification" in content_lower
            
            if has_rca and has_proposed and has_verification:
                with open(self.plan_path, "w") as f:
                    f.write(plan_content)
                break
            else:
                logger.warning(f"Draft plan failed constraint validation (Attempt {attempt}/3). Retrying...")
                missing = []
                if not has_rca: missing.append("Root Cause Analysis (RCA)")
                if not has_proposed: missing.append("Proposed Changes")
                if not has_verification: missing.append("Verification Plan")
                self.memory_context += f"\n\n[System Correction Alert]: The plan draft was missing: {', '.join(missing)}. Please include all mandatory sections."
        else:
            raise ValueError("Swarm failed to generate a valid implementation plan after 3 attempts.")
            
        if not os.path.exists(self.task_path):
            with open(self.task_path, "w") as f:
                f.write("# Task Tracking\n\n- [ ] Task initialized.\n")

        # Approval Gate
        logger.info(f"🛑 [APPROVAL GATE] Please review {self.plan_path}.")
        self._update_live_status("Approval", "Orchestrator", "🛑 Phase 2: Planning (Waiting for User Approval)")
        user_input = await asyncio.to_thread(input, "Approve plan and authorize execution? (yes/no): ")
        if user_input.strip().lower() in ["yes", "y"]:
            self.approved = True
        else:
            logger.warning("Plan rejected. Halting execution.")
            return

        logger.info("💻 [PHASE 3: EXECUTION] Spawning Builder to implement code changes...")
        self._update_live_status("Execution", "Builder", "💻 Phase 3: Execution (Implementing code)")
        build_instr = load_agent_instructions("builder")
        if self.memory_context:
            build_instr += f"\n\n## 🧠 RECALLED MISSION WISDOM\n{self.memory_context}"

        builder_config = LocalAgentConfig.load_from_workspace(  # type: ignore
            agent_role="builder",
            system_instructions=build_instr,
            capabilities=types.CapabilitiesConfig(enable_subagents=True),
            max_turns=5
        )
        async with Agent(builder_config) as builder:
            exec_resp = await builder.chat(
                f"Execute changes outlined in '{self.plan_path}' and update status in '{self.task_path}'."
            )
            print(await exec_resp.text())

        # Compile validation
        logger.info("⚙️ [SYNTAX CHECK] Compiling Python files...")
        import py_compile
        
        validation_failed = False
        failed_file = ""
        error_msg = ""
        
        ignore_dirs = {".venv", "venv", ".git", "__pycache__"}
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in ignore_dirs]
            for file in files:
                if file.endswith(".py"):
                    full_path = os.path.join(root, file)
                    try:
                        py_compile.compile(full_path, doraise=True)
                    except py_compile.PyCompileError as e:
                        validation_failed = True
                        failed_file = full_path
                        error_msg = str(e)
                        break
            if validation_failed:
                break

        # Verification Phase & Rollback Gate
        if validation_failed:
            logger.error(f"🛡️ [ESCALATION GATE] Verification failed on {failed_file}: {error_msg}")
            self._update_live_status("Rollback", "Librarian", f"⚠️ Verification Failed: Reverting changes due to compilation error in {failed_file}")
            
            # Execute automated rollback (exclude native_orchestrator.py to preserve code fixes)
            logger.info("Reverting modified files to last stable state...")
            import subprocess
            try:
                result = subprocess.run(
                    ["git", "diff", "--name-only"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                modified_files = [f.strip() for f in result.stdout.splitlines() if f.strip()]
                exempt_files = {"native_orchestrator.py", ".env", "mcp_config.json"}
                files_to_revert = [f for f in modified_files if os.path.basename(f) not in exempt_files]
                if files_to_revert:
                    logger.info(f"Reverting files: {files_to_revert}")
                    subprocess.run(["git", "checkout", "--"] + files_to_revert, check=True)
            except Exception as rollback_err:
                logger.error(f"Failed to execute rollback: {rollback_err}")
            
            logger.error("Swarm execution halted and rolled back.")
            sys.exit(1)

        logger.info("🛡️ [PHASE 4: VERIFICATION] Spawning Librarian for final sync...")
        self._update_live_status("Verification", "Librarian", "🛡️ Phase 4: Verification (Validating changes)")
        lib_instr = load_agent_instructions("librarian")
        if self.memory_context:
            lib_instr += f"\n\n## 🧠 RECALLED MISSION WISDOM\n{self.memory_context}"

        lib_config = LocalAgentConfig.load_from_workspace(  # type: ignore
            agent_role="librarian",
            system_instructions=lib_instr,
            capabilities=types.CapabilitiesConfig(enable_subagents=True),
            max_turns=5
        )
        async with Agent(lib_config) as librarian:
            sync_resp = await librarian.chat(
                f"Verify changes, write '{self.walkthrough_path}', and sync state to Supabase."
            )
            print(await sync_resp.text())
        logger.info("🎉 Swarm execution workflow successfully completed!")
        self._update_live_status("Success", "Librarian", "🎉 Success (Swarm workflow successfully completed!)")

async def main():
    if len(sys.argv) < 2:
        print("Usage: python native_orchestrator.py \"<task description>\"")
        sys.exit(1)
    task = sys.argv[1]
    orchestrator = SwarmOrchestrator(task)
    await orchestrator.execute_workflow()

if __name__ == "__main__":
    asyncio.run(main())
