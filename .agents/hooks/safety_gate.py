##!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys

HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HOOK_DIR, "../.."))
HOME_DIR = os.path.expanduser("~")


def main():
    try:
        # 1. Non-blocking Stream Protection
        if sys.stdin.isatty():
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": "Safety gate validation error: Script cannot run in an interactive terminal.",
                    }
                ),
                flush=True,
            )
            return

        # Read the tool call details from stdin
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"decision": "allow"}), flush=True)
            return

        payload = json.loads(input_data)
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name")
        arguments = tool_call.get("args", {})
        artifact_dir = payload.get("artifactDirectoryPath")
        transcript_path = payload.get("transcriptPath")
        if not artifact_dir and transcript_path:
            artifact_dir = os.path.abspath(
                os.path.join(os.path.dirname(transcript_path), "../..")
            )
    except Exception as e:
        # Fail closed on parse errors + immediate flush
        print(
            json.dumps(
                {
                    "decision": "deny",
                    "reason": f"Safety gate validation failed to parse input: {e!s}",
                }
            ),
            flush=True,
        )
        return

    # 0. Loop Protection Guards (Runaway Loops & Cost Guardrails)
    initial_num_steps = payload.get("initialNumSteps", 0)
    if initial_num_steps >= 150:
        print(
            json.dumps(
                {
                    "decision": "deny",
                    "reason": f"Runaway Loop Guard: Agent has exceeded 150 steps ({initial_num_steps}). Execution halted to prevent quota waste.",
                }
            ),
            flush=True,
        )
        return

    transcript_path = payload.get("transcriptPath")
    if transcript_path and os.path.exists(transcript_path):
        try:
            with open(transcript_path, encoding="utf-8") as f:
                lines = f.readlines()

            error_count = 0
            # Scan recent history backwards
            for line in reversed(lines[-60:]):
                try:
                    step_data = json.loads(line.strip())
                    s_type = step_data.get("type", "")

                    if s_type in ["TOOL_OUTPUT", "PLANNER_RESPONSE", "TOOL_RESPONSE"]:
                        content_str = str(step_data.get("content", "")).lower()
                        status = str(step_data.get("status", ""))

                        if (
                            status == "ERROR"
                            or "error invalid tool call" in content_str
                            or "the command failed with exit code" in content_str
                        ):
                            error_count += 1
                        else:
                            # A successful tool output breaks the consecutive error chain
                            if s_type != "PLANNER_RESPONSE":
                                break
                except Exception:
                    continue

            if error_count >= 3:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": "Cost Guardrail: 3 consecutive tool failures detected in transcript. Halting all execution loops.",
                        }
                    ),
                    flush=True,
                )
                return
        except Exception:
            pass  # Fail open on read errors

    # 1. Prohibited Directories (Access Protection)
    prohibited_folders = [".venv", ".git", "venv", "node_modules"]
    paths_to_check = []
    for arg_name in [
        "Path",
        "path",
        "AbsolutePath",
        "DirectoryPath",
        "TargetFile",
        "SearchPath",
        "SearchDirectory",
        "file_path",
    ]:
        if arg_name in arguments and isinstance(arguments[arg_name], str):
            paths_to_check.append(arguments[arg_name])

    for file_path in paths_to_check:
        normalized_path = file_path.replace("\\", "/")
        parts = normalized_path.split("/")
        if any(folder in parts for folder in prohibited_folders):
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": f"Access to prohibited directory path '{file_path}' is blocked.",
                    }
                ),
                flush=True,
            )
            return

    # 2. Destructive Commands & Shell Guardrails
    if tool_name in ["run_command", "execute_command"]:
        # Fallback to alternative common naming variants for the command arg
        cmd = (
            arguments.get("CommandLine")
            or arguments.get("command")
            or arguments.get("cmd")
            or ""
        ).strip()
        cmd_lower = cmd.lower()

        # Dangerous file deletion checks (use regex word boundaries to avoid false positives like 'dino-platform')
        is_rm_cmd = bool(
            re.search(r"(?:^|[;&|\s/])rm(?:\s+|$)", cmd_lower)
            or re.search(r"(?:^|[;&|\s/])rmdir(?:\s+|$)", cmd_lower)
        )
        if is_rm_cmd:
            # Block any rm command unless restricted to temp/safe folders
            if not any(safe_p in cmd_lower for safe_p in ["/tmp/", "scratch/"]):
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": f"Destructive command blocked: execution of '{cmd}' is prohibited.",
                        }
                    ),
                    flush=True,
                )
                return

        # Git history protection
        if "git " in cmd_lower and (
            "reset --hard" in cmd_lower
            or ("push" in cmd_lower and "--force" in cmd_lower)
        ):
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": "Destructive Git operations (hard resets, force pushes) are blocked.",
                    }
                ),
                flush=True,
            )
            return

        # Git Hygiene & Secret Guard
        if any(
            pat in cmd_lower
            for pat in ["git add .", "git add -a", "git add --all", "git add *"]
        ):
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": "Git Hygiene Guardrail: Blanket 'git add .' is blocked to prevent accidental staging of .env files or credentials. Please stage specific target files explicitly (e.g. 'git add path/to/file').",
                    }
                ),
                flush=True,
            )
            return

        if "git commit" in cmd_lower and ".env" in cmd_lower:
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": "Credentials Guardrail: Staging or committing .env or credential files is strictly prohibited.",
                    }
                ),
                flush=True,
            )
            return

        # Dependency Control & Package Hygiene Guard
        if any(
            pkg_cmd in cmd_lower
            for pkg_cmd in ["pip install", "npm install", "yarn add", "pnpm add"]
        ):
            if not any(
                safe_prefix in cmd_lower
                for safe_prefix in [".venv/bin/pip", "--help", "-h"]
            ):
                print(
                    json.dumps(
                        {
                            "decision": "force_ask",
                            "reason": "Dependency Control Guardrail: Package installation commands should use the project virtual environment (.venv/bin/pip). Authorize this package operation?",
                        }
                    ),
                    flush=True,
                )
                return

    # 3. Quota Optimization Guards & Token Hygiene (Broad Searches & File Sizing)
    if tool_name in ["view_file", "read_file"]:
        file_path = (
            arguments.get("AbsolutePath")
            or arguments.get("Path")
            or arguments.get("path")
            or ""
        )
        binary_exts = [
            ".png",
            ".jpg",
            ".jpeg",
            ".pdf",
            ".webp",
            ".gif",
            ".mp4",
            ".mp3",
            ".tar",
            ".zip",
            ".gz",
        ]
        if file_path and not any(
            file_path.lower().endswith(ext) for ext in binary_exts
        ):
            if os.path.exists(file_path) and os.path.getsize(file_path) > 50 * 1024:
                has_pagination = (
                    "StartLine" in arguments and arguments["StartLine"] is not None
                ) or ("EndLine" in arguments and arguments["EndLine"] is not None)
                if not has_pagination:
                    size_kb = round(os.path.getsize(file_path) / 1024, 1)
                    print(
                        json.dumps(
                            {
                                "decision": "force_ask",
                                "reason": f"Token Truncation Guardrail: File size ({size_kb} KB) exceeds 50 KB. View without pagination?",
                            }
                        ),
                        flush=True,
                    )
                    return

    if tool_name in ["grep_search", "list_dir", "find_by_name"]:
        path_arg = (
            arguments.get("SearchPath")
            or arguments.get("DirectoryPath")
            or arguments.get("SearchDirectory")
            or arguments.get("path")
            or ""
        )
        # Strip trailing slashes for clean string matching
        path_arg_clean = path_arg.rstrip("/")

        # Block scanning workspace root or home too broadly
        if path_arg_clean in ["", "/", "/home", HOME_DIR, PROJECT_ROOT]:
            if tool_name == "grep_search":
                # Look for alternative common variations of "Query"
                query_arg = (
                    arguments.get("Query")
                    or arguments.get("query")
                    or arguments.get("pattern")
                    or ""
                )
                if query_arg in ["", "*", ".*"] or len(query_arg) < 2:
                    print(
                        json.dumps(
                            {
                                "decision": "force_ask",
                                "reason": "Token Hygiene: Broad grep search on workspace root may consume significant tokens. Authorize this scan?",
                            }
                        ),
                        flush=True,
                    )
                    return
            elif tool_name in ["list_dir", "find_by_name"] and path_arg_clean in [
                "",
                "/",
                "/home",
                HOME_DIR,
            ]:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": "Listing system root directories is blocked to prevent token waste.",
                        }
                    ),
                    flush=True,
                )
                return

    # 4. Plan Approval Gate / Root Cause Gate (Writing/modifying files) + MCP Config Protection
    write_tools = [
        "write_file",
        "edit_file",
        "write_to_file",
        "replace_file_content",
        "multi_replace_file_content",
        "delete_file",
    ]
    if tool_name in write_tools:
        target_file = (
            arguments.get("TargetFile")
            or arguments.get("file_path")
            or arguments.get("Path")
            or arguments.get("path")
            or ""
        )
        target_basename = os.path.basename(target_file)

        # MCP Configuration Lock & Boundary Protection
        if "mcp_config.json" in target_basename:
            print(
                json.dumps(
                    {
                        "decision": "deny",
                        "reason": "MCP Configuration Lock: Modifications to all mcp_config.json files are strictly locked. Please make any configuration changes manually.",
                    }
                ),
                flush=True,
            )
            return

        # Hook File Self-Protection Lock
        hooks_dir = os.path.join(PROJECT_ROOT, ".agents", "hooks")
        if target_file.startswith(hooks_dir):
            print(
                json.dumps(
                    {
                        "decision": "force_ask",
                        "reason": "Hook Infrastructure Lock: Modifications to lifecycle hooks (.agents/hooks/*) require explicit authorization. Authorize this hook edit?",
                    }
                ),
                flush=True,
            )
            return

        # Don't restrict writing to plan/task/walkthrough files or isolated brain scratch sandbox scripts
        is_brain_scratch = (
            bool(artifact_dir)
            and target_file.startswith(os.path.join(artifact_dir, "scratch"))
        ) or (
            (
                "/.gemini/antigravity-ide/brain/" in target_file
                or "/.gemini/antigravity/brain/" in target_file
            )
            and "/scratch/" in target_file
        )
        if (
            target_basename
            not in [
                "implementation_plan.md",
                "task.md",
                "walkthrough.md",
                "review_findings.md",
            ]
            and not is_brain_scratch
        ):
            plan_file = "implementation_plan.md"

            # Formulate potential paths for the implementation plan
            paths_to_check = []
            if artifact_dir:
                paths_to_check.append(os.path.join(artifact_dir, plan_file))
            paths_to_check.append(os.path.join(PROJECT_ROOT, plan_file))
            paths_to_check.append(plan_file)

            plan_to_read = None
            for p in paths_to_check:
                if os.path.exists(p):
                    plan_to_read = p
                    break

            if not plan_to_read:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": "Plan Approval Gate: 'implementation_plan.md' must exist before modifying code files.",
                        }
                    ),
                    flush=True,
                )
                return

            try:
                with open(plan_to_read, encoding="utf-8") as f:
                    content = f.read().lower()
                has_rca = "root cause" in content or "rca" in content
                has_proposed = (
                    "proposed changes" in content
                    or "proposed" in content
                    or "plan" in content
                )
                has_verification = (
                    "verification plan" in content or "verification" in content
                )

                # Verify approval and workflow status from transcript sequence
                approval_after_latest_user = False
                latest_user_prompt = ""
                latest_user_index = -1
                latest_approval_index = -1

                if transcript_path and os.path.exists(transcript_path):
                    with open(transcript_path, encoding="utf-8") as tf:
                        t_lines = tf.readlines()

                    # Scan forward to index user prompts and approvals chronologically
                    for idx, line in enumerate(t_lines):
                        try:
                            line_str = line.lower()
                            if "the user has approved this document" in line_str:
                                latest_approval_index = idx

                            step_data = json.loads(line.strip())
                            s_type = step_data.get("type", "")
                            if s_type == "USER_INPUT":
                                prompt_val = step_data.get("content", "")
                                prompt_str = (
                                    prompt_val
                                    if isinstance(prompt_val, str)
                                    else str(prompt_val)
                                ).strip()
                                # Filter out system approval injection strings
                                if (
                                    prompt_str
                                    and prompt_str != "<USER_REQUEST></USER_REQUEST>"
                                    and "<user_request>\n\n</user_request>"
                                    not in prompt_str
                                    and "the user has approved this document"
                                    not in prompt_str.lower()
                                ):
                                    latest_user_prompt = prompt_str.lower()
                                    latest_user_index = idx
                                    req_match = re.search(
                                        r"<user_request>(.*?)</user_request>",
                                        latest_user_prompt,
                                        re.DOTALL,
                                    )
                                    clean_msg = (
                                        req_match.group(1).strip()
                                        if req_match
                                        else latest_user_prompt.strip()
                                    )
                                    if not clean_msg.startswith("/") and re.match(
                                        r"^(?:yes[, ]+)?(?:please )?(?:approve|approved|proceed|lgtm|go ahead|yes fix it|run it)[.!]*$",
                                        clean_msg,
                                    ):
                                        latest_approval_index = idx
                        except Exception:
                            if "the user has approved this document" in line.lower():
                                latest_approval_index = idx
                            continue

                # Approval is only valid if explicit approval occurred AFTER or AT the latest user request
                if (
                    latest_approval_index > -1
                    and latest_approval_index >= latest_user_index
                ):
                    approval_after_latest_user = True

                # Plan Integrity Fingerprinting: Guard against post-approval plan tampering
                if artifact_dir and os.path.exists(artifact_dir):
                    plan_hash_file = os.path.join(artifact_dir, ".approved_plan_hash")
                else:
                    plan_hash_file = os.path.join(
                        PROJECT_ROOT, ".agents", "hooks", ".approved_plan_hash"
                    )
                current_plan_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                if approval_after_latest_user:
                    if os.path.exists(plan_hash_file):
                        try:
                            with open(plan_hash_file, encoding="utf-8") as hf:
                                stored_parts = hf.read().strip().split(":", 1)
                                stored_hash = stored_parts[0]
                                stored_idx = (
                                    int(stored_parts[1])
                                    if len(stored_parts) > 1
                                    else -1
                                )
                        except Exception:
                            stored_hash, stored_idx = "", -1

                        if (
                            stored_idx == latest_approval_index
                            and stored_hash != current_plan_hash
                        ):
                            print(
                                json.dumps(
                                    {
                                        "decision": "force_ask",
                                        "reason": "Plan Integrity Guardrail: 'implementation_plan.md' was modified after user approval. Re-authorize the updated plan to continue?",
                                    }
                                ),
                                flush=True,
                            )
                            return
                        elif stored_idx != latest_approval_index:
                            with open(plan_hash_file, "w", encoding="utf-8") as hf:
                                hf.write(f"{current_plan_hash}:{latest_approval_index}")
                    else:
                        try:
                            with open(plan_hash_file, "w", encoding="utf-8") as hf:
                                hf.write(f"{current_plan_hash}:{latest_approval_index}")
                        except Exception:
                            pass

                # 4a. Read-only Workflow Gate Check
                if not approval_after_latest_user:
                    readonly_workflows = ["/review", "/audit", "/consult"]
                    if any(wf in latest_user_prompt for wf in readonly_workflows):
                        print(
                            json.dumps(
                                {
                                    "decision": "deny",
                                    "reason": "Read-only Workflow Gate: Code modifications are strictly prohibited during read-only workflows.",
                                }
                            ),
                            flush=True,
                        )
                        return

                has_approval = approval_after_latest_user

                if not (has_rca and has_proposed and has_verification):
                    print(
                        json.dumps(
                            {
                                "decision": "deny",
                                "reason": "Plan Approval Gate: 'implementation_plan.md' must document Root Cause Analysis (RCA), Proposed Changes, and a Verification Plan.",
                            }
                        ),
                        flush=True,
                    )
                    return
                if not has_approval:
                    print(
                        json.dumps(
                            {
                                "decision": "deny",
                                "reason": "Plan Approval Gate: User approval missing. Please click the blue Proceed button to authorize changes or tag status as approved.",
                            }
                        ),
                        flush=True,
                    )
                    return

                # 4b. Proactive Documentation Lookup Enforcement (Context7 / Modern Web Guidance / Google Developer Knowledge / Exa)
                code_exts = [
                    ".ts",
                    ".tsx",
                    ".js",
                    ".jsx",
                    ".py",
                    ".html",
                    ".css",
                    ".go",
                    ".rs",
                    ".java",
                    ".c",
                    ".cpp",
                    ".h",
                    ".sh",
                    ".bash",
                ]
                ext = os.path.splitext(target_file)[1].lower()

                # Exclusion filter: Skip non-code files (.md, .json, .yaml, .yml, .env, .csv, .log)
                # and internal agent system infrastructure (.agents/)
                is_internal_agent_file = "/.agents/" in target_file.replace(
                    "\\", "/"
                ) or target_file.startswith(os.path.join(PROJECT_ROOT, ".agents"))
                is_code_file = (ext in code_exts) and not is_internal_agent_file

                if is_code_file and transcript_path and os.path.exists(transcript_path):
                    has_doc_lookup = False
                    try:
                        with open(transcript_path, encoding="utf-8") as tf:
                            for line in tf:
                                l_str = line.lower()
                                if any(
                                    term in l_str
                                    for term in [
                                        "query-docs",
                                        "resolve-library-id",
                                        "context7",
                                        "modern-web-guidance",
                                        "google-developer-knowledge",
                                        "retrieving-developer-knowledge",
                                        "answer_query",
                                        "search_documents",
                                        "get_documents",
                                        "developerknowledge.googleapis.com",
                                        "web_search_exa",
                                        "search_web",
                                    ]
                                ):
                                    has_doc_lookup = True
                                    break
                    except Exception:
                        has_doc_lookup = True  # Fail open on transcript read exception to prevent deadlock

                    if not has_doc_lookup:
                        print(
                            json.dumps(
                                {
                                    "decision": "deny",
                                    "reason": "Documentation Guardrail: Must execute Context7 MCP, Modern Web Guidance, or Google Developer Knowledge search prior to modifying code files.",
                                }
                            ),
                            flush=True,
                        )
                        return
            except Exception as e:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": f"Plan Approval Gate: Failed to read implementation plan or transcript: {e!s}",
                        }
                    ),
                    flush=True,
                )
                return

    # 5. Database Modification Checks & BigQuery MCP Cost Ceiling
    is_bq_mcp = (
        tool_name == "call_mcp_tool" and arguments.get("ServerName") == "bigquery"
    )
    bq_tool = arguments.get("ToolName") if is_bq_mcp else tool_name
    bq_args = arguments.get("Arguments", {}) if is_bq_mcp else arguments

    if bq_tool in ["execute_sql", "execute_sql_readonly"] or tool_name in [
        "execute_sql",
        "execute_sql_readonly",
    ]:
        raw_query = (
            bq_args.get("query") or bq_args.get("sql") or arguments.get("query") or ""
        ).strip()
        is_dry_run = bq_args.get("dryRun", False) or arguments.get("dryRun", False)
        normalized_query = " ".join(raw_query.upper().split())

        # 5a. Block destructive mutations
        write_keywords = [
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "DROP ",
            "CREATE ",
            "ALTER ",
            "REPLACE ",
            "TRUNCATE ",
        ]
        if any(kw in normalized_query for kw in write_keywords):
            if bq_tool != "execute_sql_readonly":
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": "Database Safety Guardrail: Mutating SQL queries (INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE) are blocked by default.",
                        }
                    ),
                    flush=True,
                )
                return

        # 5b. Block unbounded public dataset scans on live execution (dryRun is exempt)
        if not is_dry_run and "BIGQUERY-PUBLIC-DATA" in normalized_query:
            has_wildcard = (
                "SELECT *" in normalized_query or "SELECT ALL *" in normalized_query
            )
            has_bound = "WHERE " in normalized_query or "LIMIT " in normalized_query
            if has_wildcard and not has_bound:
                print(
                    json.dumps(
                        {
                            "decision": "deny",
                            "reason": "BigQuery Cost Guardrail: Unbounded 'SELECT *' queries against bigquery-public-data without a WHERE or LIMIT clause are blocked. Please add filters, limit rows, or run with dryRun: true first.",
                        }
                    ),
                    flush=True,
                )
                return

    # Default: Allow the tool execution
    print(json.dumps({"decision": "allow"}), flush=True)


if __name__ == "__main__":
    main()
