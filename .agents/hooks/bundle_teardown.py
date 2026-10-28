#!/usr/bin/env python3
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime


def log(msg: str) -> None:
    sys.stderr.write(f"[Teardown] {msg}\n")
    sys.stderr.flush()


def get_project_root() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", ".."))


def archive_lessons_supabase(project_root: str) -> None:
    try:
        home_dir = os.path.expanduser("~")
        brain_dirs = [
            os.path.join(home_dir, ".gemini/antigravity/brain"),
            os.path.join(home_dir, ".gemini/antigravity-ide/brain"),
        ]
        candidates = []
        for brain_dir in brain_dirs:
            if os.path.exists(brain_dir):
                for conv in os.listdir(brain_dir):
                    candidate = os.path.join(brain_dir, conv, "walkthrough.md")
                    if os.path.exists(candidate):
                        candidates.append(candidate)
        walkthrough_path = max(candidates, key=os.path.getmtime) if candidates else None
        if not walkthrough_path:
            candidate = os.path.join(project_root, "walkthrough.md")
            if os.path.exists(candidate):
                walkthrough_path = candidate
        if not walkthrough_path:
            return

        with open(walkthrough_path, encoding="utf-8") as f:
            content = f.read()

        hash_path = os.path.join(project_root, ".agents/hooks/.walkthrough_hash")
        curr_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if os.path.exists(hash_path):
            with open(hash_path) as hf:
                if hf.read().strip() == curr_hash:
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

        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        topic = title_match.group(1) if title_match else "Session Walkthrough"
        lesson_payload = {
            "topic": topic,
            "content": content[:4000],
            "tags": ["session_walkthrough", "auto_archived"],
            "metadata": {
                "source": "bundle_teardown",
                "timestamp": datetime.now().isoformat(),
            },
        }

        if supabase_url and supabase_key:
            if not supabase_url.lower().startswith("https://"):
                log(
                    "Aborting Supabase lesson archival: Insecure HTTP protocol detected for SUPABASE_URL."
                )
                return
            try:
                headers = {
                    "apikey": supabase_key,
                    "Authorization": f"Bearer {supabase_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                }
                req = urllib.request.Request(
                    f"{supabase_url}/rest/v1/lessons_learned",
                    data=json.dumps(lesson_payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status in (200, 201):
                        with open(hash_path, "w") as hf:
                            hf.write(curr_hash)
                        log("Archived lesson to Supabase successfully.")
                        return
            except Exception:
                pass

        pending_path = os.path.join(project_root, "pending_lessons.json")
        pending_list = []
        if os.path.exists(pending_path):
            try:
                with open(pending_path) as pf:
                    loaded = json.load(pf)
                    pending_list = (
                        loaded
                        if isinstance(loaded, list)
                        else loaded.get("pending", [])
                    )
            except Exception:
                pass
        pending_list.append(lesson_payload)
        with open(pending_path, "w", encoding="utf-8") as pf:
            json.dump({"pending": pending_list}, pf, indent=2)
        with open(hash_path, "w") as hf:
            hf.write(curr_hash)
        log("Queued lesson in pending_lessons.json for offline retry.")
    except Exception as e:
        log(f"Archival warning: {e}")


def handle_failure_alerts(project_root: str, payload: dict) -> None:
    try:
        term_reason = (
            str(payload.get("terminationReason", "")).strip()
            or os.environ.get("AG_EXIT_STATUS", "").strip()
        )
        task_id = (
            str(payload.get("conversationId", "")).strip()
            or os.environ.get("AG_TASK_ID", "").strip()
        )
        last_error = (
            str(payload.get("error", "")).strip()
            or os.environ.get("AG_LAST_ERROR", "").strip()
        )
        if term_reason in ("ERROR", "failure") or last_error:
            log_path = os.path.join(project_root, "failure_log.txt")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            entry = f"[{timestamp}] Task: {task_id or 'N/A'}\nError: {last_error or 'None'}\n{'-' * 40}\n"
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
    except Exception:
        pass


def cleanup_temp_files(project_root: str) -> None:
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        temp_targets = [
            os.path.join(project_root, "debug_hook_payload.json"),
            os.path.join(script_dir, ".debug_prompt_payload.json"),
        ]
        for p in temp_targets:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
        pycache = os.path.join(script_dir, "__pycache__")
        if os.path.exists(pycache):
            try:
                shutil.rmtree(pycache)
            except Exception:
                pass
    except Exception:
        pass


def main() -> None:
    project_root = get_project_root()
    payload = {}
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                payload = json.loads(raw)
        except Exception:
            pass
    archive_lessons_supabase(project_root)
    handle_failure_alerts(project_root, payload)
    cleanup_temp_files(project_root)
    print(json.dumps({}), flush=True)


if __name__ == "__main__":
    main()
