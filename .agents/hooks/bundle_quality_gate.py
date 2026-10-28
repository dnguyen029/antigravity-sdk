#!/usr/bin/env python3
import json
import os
import re
import subprocess
import sys


def log(msg: str) -> None:
    sys.stderr.write(f"[QualityGate] {msg}\n")
    sys.stderr.flush()


def get_project_root() -> str:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(script_dir, "..", ".."))


def check_markdown_file(file_path: str) -> None:
    if not os.path.exists(file_path):
        return
    normalized = file_path.replace("\\", "/")
    if "/brain/" in normalized or "/.gemini/" in normalized:
        return

    try:
        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        log(f"Could not read {file_path}: {e}")
        return

    link_pattern = re.compile(r"!?\[([^\]]*)\]\(([^)]+)\)")
    matches = link_pattern.findall(content)

    broken_links = []
    for text, link in matches:
        clean_link = link.split("#")[0].strip()
        display_text = text.lstrip("!")
        if not clean_link:
            continue

        target_path = None
        if clean_link.startswith("file://"):
            target_path = clean_link.replace("file://", "")
        elif not clean_link.startswith(("http://", "https://", "mailto:", "ftp://")):
            if clean_link.startswith("/"):
                target_path = clean_link
            else:
                target_path = os.path.normpath(
                    os.path.join(os.path.dirname(file_path), clean_link)
                )

        if target_path and not os.path.exists(target_path):
            broken_links.append((display_text, link, target_path))

    if broken_links:
        log(
            f"Warning: {len(broken_links)} broken link(s) in {os.path.basename(file_path)}:"
        )
        for text, link, target in broken_links[:5]:
            log(f"  - [{text}] -> Missing: {target}")
    else:
        log(f"Link check OK for {os.path.basename(file_path)}.")


def check_python_file(file_path: str, project_root: str) -> None:
    if not os.path.exists(file_path):
        return
    venv_bin = os.path.join(project_root, ".venv", "bin")
    ruff_bin = os.path.join(venv_bin, "ruff")

    try:
        if os.path.exists(ruff_bin):
            subprocess.run(
                [ruff_bin, "format", "--", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
            subprocess.run(
                [ruff_bin, "check", "--fix", "--", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
        else:
            subprocess.run(
                [
                    "uv",
                    "run",
                    "--with",
                    "ruff",
                    "ruff",
                    "check",
                    "--fix",
                    "--",
                    file_path,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
            )
    except subprocess.TimeoutExpired:
        log(f"Ruff check/format timed out after 15s on {os.path.basename(file_path)}.")
    except Exception as e:
        log(f"Ruff invocation warning: {e}")

    pytest_bin = os.path.join(venv_bin, "pytest")
    if os.path.exists(pytest_bin):
        basename = os.path.basename(file_path)
        test_target = None
        if basename.startswith("test_") or basename.endswith("_test.py"):
            test_target = file_path
        else:
            candidate = os.path.join(os.path.dirname(file_path), f"test_{basename}")
            if os.path.exists(candidate):
                test_target = candidate

        if test_target:
            log(f"Running targeted test: {os.path.basename(test_target)}")
            try:
                subprocess.run(
                    [pytest_bin, "--", test_target],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=30,
                )
            except subprocess.TimeoutExpired:
                log(f"Pytest timed out after 30s on {os.path.basename(test_target)}.")
            except Exception as e:
                log(f"Pytest execution warning: {e}")


def main() -> None:
    project_root = get_project_root()
    target_file = ""

    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
            if raw.strip():
                payload = json.loads(raw)
                args = payload.get("toolCall", {}).get("args", {})
                target_file = (
                    args.get("TargetFile")
                    or args.get("FilePath")
                    or args.get("Path")
                    or args.get("path")
                    or ""
                )
        except Exception:
            pass

    if not target_file:
        target_file = (
            os.environ.get("AG_TOOL_ARG_TargetFile")
            or os.environ.get("AG_TOOL_ARG_FilePath")
            or os.environ.get("AG_TOOL_ARG_Path")
            or ""
        )
    if not target_file and len(sys.argv) > 1:
        target_file = sys.argv[1]

    if target_file:
        if target_file.endswith(".md"):
            check_markdown_file(target_file)
        elif target_file.endswith(".py"):
            check_python_file(target_file, project_root)

    print(json.dumps({}), flush=True)


if __name__ == "__main__":
    main()
