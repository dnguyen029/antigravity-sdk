#!/usr/bin/env python3
import glob
import json
import os
import re
import signal
import sys
import urllib.parse
import urllib.request


def log(msg: str) -> None:
    sys.stderr.write(f"[PreInvocation] {msg}\n")
    sys.stderr.flush()


def get_project_root() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", ".."))


def sync_implicit_pb() -> None:
    try:
        home_dir = os.path.expanduser("~")
        synced = 0
        for app_folder in [".gemini/antigravity-ide", ".gemini/antigravity"]:
            base_dir = os.path.join(home_dir, app_folder)
            implicit_dir = os.path.join(base_dir, "implicit")
            conv_dir = os.path.join(base_dir, "conversations")
            if os.path.isdir(implicit_dir) and os.path.isdir(conv_dir):
                pb_files = glob.glob(os.path.join(implicit_dir, "*.pb"))
                for pb_path in pb_files:
                    filename = os.path.basename(pb_path)
                    dest_path = os.path.join(conv_dir, filename)
                    if not os.path.exists(dest_path) and not os.path.islink(dest_path):
                        try:
                            os.symlink(pb_path, dest_path)
                            synced += 1
                        except Exception:
                            pass
        if synced > 0:
            log(f"Linked {synced} implicit PB file(s).")
    except Exception as e:
        log(f"PB sync warning: {e}")


def run_mcp_hygiene(project_root: str) -> None:
    if os.environ.get("BYPASS_MCP_VERIFICATION") == "1":
        return
    try:
        config_path = os.path.join(project_root, "mcp_config.json")
        if not os.path.exists(config_path):
            config_path = os.path.expanduser("~/.gemini/antigravity/mcp_config.json")
        if not os.path.exists(config_path):
            config_path = os.path.expanduser(
                "~/.gemini/antigravity-ide/mcp_config.json"
            )
        if not os.path.exists(config_path):
            return

        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        servers = config.get("mcpServers", {})

        mcp_signatures = set()
        for name, srv in servers.items():
            cmd = srv.get("command") or ""
            base_cmd = os.path.basename(cmd)
            if "mcp" in base_cmd.lower():
                mcp_signatures.add(base_cmd)

            for arg in srv.get("args", []):
                if not arg or not isinstance(arg, str):
                    continue
                if "mcp.exa.ai" in arg:
                    mcp_signatures.add("mcp.exa.ai")
                if "mcp.supabase.com" in arg:
                    mcp_signatures.add("mcp.supabase.com")
                if "@retailerapi/mcp" in arg:
                    mcp_signatures.add("@retailerapi/mcp")
                if "mcp-remote" in arg:
                    mcp_signatures.add("mcp-remote")
                if "mcp-server-toon" in arg or "toon-mcp" in arg:
                    mcp_signatures.add("mcp-server-toon")
                if "markitdown_mcp" in arg:
                    mcp_signatures.add("markitdown_mcp")

                if "/" in arg:
                    base_arg = os.path.basename(arg)
                    if base_arg.endswith(".py") and (
                        "mcp" in base_arg.lower()
                        or "conversational_agents" in base_arg
                        or "context" in base_arg
                    ):
                        mcp_signatures.add(base_arg)
                elif arg.endswith(".py") and (
                    "mcp" in arg.lower()
                    or "conversational_agents" in arg
                    or "context" in arg
                ):
                    mcp_signatures.add(arg)

        if not mcp_signatures or not os.path.exists("/proc"):
            return

        active_ls_pids = set()
        for pid_str in os.listdir("/proc"):
            if not pid_str.isdigit():
                continue
            try:
                with open(f"/proc/{pid_str}/cmdline", errors="ignore") as f:
                    cmdline = f.read().replace("\x00", " ")
                if "language_server" in cmdline:
                    active_ls_pids.add(int(pid_str))
            except Exception:
                continue

        def matches_mcp(cmd: str) -> bool:
            for sig in mcp_signatures:
                pattern = rf'(?:^|[\s/"\']){re.escape(sig)}(?:$|[\s/"\'])'
                if re.search(pattern, cmd, re.IGNORECASE):
                    return True
            return False

        my_pid = os.getpid()
        killed = 0
        for pid_str in os.listdir("/proc"):
            if not pid_str.isdigit():
                continue
            pid = int(pid_str)
            if pid == my_pid or pid in active_ls_pids:
                continue
            try:
                with open(f"/proc/{pid}/cmdline", errors="ignore") as f:
                    cmdline = f.read().replace("\x00", " ").strip()
                if matches_mcp(cmdline):
                    ppid = None
                    with open(f"/proc/{pid}/status", errors="ignore") as sf:
                        for line in sf:
                            if line.startswith("PPid:"):
                                ppid = int(line.split()[1])
                                break
                    is_descendant = False
                    curr = ppid
                    for _ in range(10):
                        if not curr or curr <= 1:
                            break
                        if curr in active_ls_pids:
                            is_descendant = True
                            break
                        next_ppid = None
                        try:
                            with open(f"/proc/{curr}/status", errors="ignore") as sf:
                                for line in sf:
                                    if line.startswith("PPid:"):
                                        next_ppid = int(line.split()[1])
                                        break
                        except Exception:
                            break
                        curr = next_ppid
                    if not is_descendant:
                        os.kill(pid, signal.SIGTERM)
                        killed += 1
            except Exception:
                continue
        if killed > 0:
            log(f"Cleaned up {killed} orphaned MCP background process(es).")
    except Exception as e:
        log(f"MCP hygiene warning: {e}")


def flush_pending_lessons(project_root: str) -> None:
    try:
        pending_path = os.path.join(project_root, "pending_lessons.json")
        if not os.path.exists(pending_path):
            return

        with open(pending_path, encoding="utf-8") as f:
            pending_data = json.load(f)

        lessons = (
            pending_data
            if isinstance(pending_data, list)
            else pending_data.get("pending", [])
        )
        if not lessons:
            return

        env_path = os.path.join(project_root, ".env")
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get(
            "SUPABASE_SERVICE_ROLE_KEY"
        )

        if os.path.exists(env_path) and (not supabase_url or not supabase_key):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SUPABASE_URL=") and not supabase_url:
                        supabase_url = line.split("=", 1)[1].strip("\"' ")
                    elif (
                        line.startswith("SUPABASE_KEY=")
                        or line.startswith("SUPABASE_SERVICE_ROLE_KEY=")
                    ) and not supabase_key:
                        supabase_key = line.split("=", 1)[1].strip("\"' ")

        if not supabase_url or not supabase_key:
            return

        if not supabase_url.lower().startswith("https://"):
            log("Aborting pending lessons flush: Insecure HTTP SUPABASE_URL detected.")
            return

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

        flushed = []
        for item in lessons:
            try:
                payload = {
                    "topic": item.get("topic")
                    or item.get("title")
                    or "General Learning",
                    "content": item.get("content") or item.get("lesson") or "",
                    "tags": item.get("tags") or ["offline_retry"],
                    "metadata": item.get("metadata") or {"source": "pending_flush"},
                }
                req = urllib.request.Request(
                    f"{supabase_url}/rest/v1/lessons_learned",
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 201):
                        flushed.append(item)
            except Exception:
                break

        if flushed:
            remaining = [l for l in lessons if l not in flushed]
            if remaining:
                with open(pending_path, "w", encoding="utf-8") as f:
                    json.dump({"pending": remaining}, f, indent=2)
            else:
                os.remove(pending_path)
            log(f"Flushed {len(flushed)} pending lesson(s) to Supabase.")
    except Exception as e:
        log(f"Lesson flush warning: {e}")


def load_lessons_context(project_root: str, user_query: str = "") -> str:
    try:
        env_path = os.path.join(project_root, ".env")
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get(
            "SUPABASE_SERVICE_ROLE_KEY"
        )
        gemini_key = os.environ.get("GEMINI_API_KEY")
        google_key = os.environ.get("GOOGLE_API_KEY")

        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("SUPABASE_URL=") and not supabase_url:
                        supabase_url = line.split("=", 1)[1].strip("\"' ")
                    elif (
                        line.startswith("SUPABASE_KEY=")
                        or line.startswith("SUPABASE_SERVICE_ROLE_KEY=")
                    ) and not supabase_key:
                        supabase_key = line.split("=", 1)[1].strip("\"' ")
                    elif line.startswith("GEMINI_API_KEY=") and not gemini_key:
                        gemini_key = line.split("=", 1)[1].strip("\"' ")
                    elif line.startswith("GOOGLE_API_KEY=") and not google_key:
                        google_key = line.split("=", 1)[1].strip("\"' ")

        active_gemini_key = gemini_key or google_key
        target_file = os.path.join(project_root, ".agents/lessons_context.md")
        if not supabase_url or not supabase_key:
            return ""

        if not supabase_url.lower().startswith("https://"):
            log("Aborting lessons context load: Insecure HTTP SUPABASE_URL detected.")
            return ""

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
        }

        semantic_records = []
        is_command = user_query.strip().startswith("/")
        word_count = len(user_query.strip().split())
        should_search = (word_count >= 3) and not is_command

        if should_search and active_gemini_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=active_gemini_key)
                emb_res = client.models.embed_content(
                    model="models/gemini-embedding-001",
                    contents=user_query.strip(),
                    config=types.EmbedContentConfig(output_dimensionality=384),
                )
                if emb_res and emb_res.embeddings:
                    query_embedding = emb_res.embeddings[0].values
                    rpc_payload = {
                        "query_embedding": query_embedding,
                        "match_threshold": 0.35,
                        "match_count": 3,
                    }
                    req = urllib.request.Request(
                        f"{supabase_url}/rest/v1/rpc/match_lessons",
                        data=json.dumps(rpc_payload).encode("utf-8"),
                        headers=headers,
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=2.5) as resp:
                        if resp.status == 200:
                            semantic_records = json.loads(resp.read().decode("utf-8"))
            except Exception as e:
                log(f"Vector search warning: {e}")

        data = semantic_records
        is_semantic = bool(semantic_records)
        if not data:
            url = f"{supabase_url}/rest/v1/lessons_learned?select=topic,content,created_at&order=created_at.desc&limit=3"
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))

        if data:
            lines = [
                f"# 🧠 Active lessons learned context ({'Semantic Match' if is_semantic else 'Recent'})\n"
            ]
            for row in data:
                topic = row.get("topic", "General")
                content = row.get("content", "")
                created = row.get("created_at", "N/A")
                lines.append(f"## 📌 {topic} (Date: {created})\n\n{content}\n")
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            with open(target_file, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        if is_semantic and semantic_records:
            top = semantic_records[0]
            return f" | Relevant Memory: {top.get('topic', '')}"
        return ""
    except Exception as e:
        log(f"Lessons context loader warning: {e}")
        return ""


def main() -> None:
    project_root = get_project_root()
    user_query = ""
    transcript_path = ""

    if not sys.stdin.isatty():
        try:
            raw_input = sys.stdin.read()
            if raw_input.strip():
                payload = json.loads(raw_input)
                transcript_path = payload.get("transcriptPath", "")
        except Exception:
            pass

    if transcript_path and os.path.exists(transcript_path):
        try:
            with open(transcript_path, encoding="utf-8") as tf:
                t_lines = tf.readlines()
            for line in reversed(t_lines[-30:]):
                step_data = json.loads(line.strip())
                if step_data.get("type") == "USER_INPUT":
                    prompt_val = step_data.get("content", "")
                    prompt_str = (
                        prompt_val if isinstance(prompt_val, str) else str(prompt_val)
                    ).strip()
                    if (
                        prompt_str
                        and "the user has approved this document"
                        not in prompt_str.lower()
                    ):
                        clean_query = re.sub(r"</?[a-zA-Z_]+>", "", prompt_str).strip()
                        if clean_query:
                            user_query = clean_query
                            break
        except Exception:
            pass

    sync_implicit_pb()
    run_mcp_hygiene(project_root)
    flush_pending_lessons(project_root)
    matched_lesson_summary = load_lessons_context(project_root, user_query)

    ephemeral_reminder = (
        "🧠 Ground Truth: Builder max retries is 3 before rollback. "
        f"Paginate files > 50KB. If denied, ask in chat{matched_lesson_summary}."
    )
    print(
        json.dumps({"injectSteps": [{"ephemeralMessage": ephemeral_reminder}]}),
        flush=True,
    )


if __name__ == "__main__":
    main()
