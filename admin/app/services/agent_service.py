import glob
import json
import logging
import os
import subprocess
import uuid

logger = logging.getLogger(__name__)

CLAUDE_BIN = os.path.expanduser("~/.local/bin/claude")

_KNPU_ROOT = "/home/lab/knpu"

PROJECT_ROOTS = {"knpu (전체)": _KNPU_ROOT}
if os.path.isdir(_KNPU_ROOT):
    for name in sorted(os.listdir(_KNPU_ROOT)):
        path = os.path.join(_KNPU_ROOT, name)
        if os.path.isdir(path) and not name.startswith("."):
            PROJECT_ROOTS[name] = path


def is_allowed_cwd(cwd: str) -> bool:
    real = os.path.realpath(cwd)
    return any(
        real == os.path.realpath(root) or real.startswith(os.path.realpath(root) + "/")
        for root in PROJECT_ROOTS.values()
    )


def _encode_cwd(cwd: str) -> str:
    return os.path.realpath(cwd).replace("/", "-")


def _transcript_path(cwd: str, session_id: str) -> str:
    return os.path.expanduser(
        f"~/.claude/projects/{_encode_cwd(cwd)}/{session_id}.jsonl"
    )


def list_live_sessions(cwd: str | None = None) -> list[dict]:
    cmd = [CLAUDE_BIN, "agents", "--json", "--all"]
    if cwd:
        cmd += ["--cwd", cwd]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return json.loads(result.stdout or "[]")
    except Exception as e:
        logger.warning(f"claude agents --json 실패: {e}")
        return []


def list_transcript_sessions(cwd: str) -> list[dict]:
    proj_dir = os.path.expanduser(f"~/.claude/projects/{_encode_cwd(cwd)}")
    if not os.path.isdir(proj_dir):
        return []

    sessions = []
    for path in glob.glob(os.path.join(proj_dir, "*.jsonl")):
        session_id = os.path.splitext(os.path.basename(path))[0]
        preview = ""
        last_ts = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if entry.get("timestamp"):
                        last_ts = entry["timestamp"]
                    if not preview and entry.get("type") == "user":
                        content = entry.get("message", {}).get("content")
                        if isinstance(content, str):
                            preview = content
                        elif isinstance(content, list):
                            for block in content:
                                if (
                                    isinstance(block, dict)
                                    and block.get("type") == "text"
                                ):
                                    preview = block.get("text", "")
                                    break
        except Exception:
            continue
        sessions.append(
            {
                "session_id": session_id,
                "preview": preview[:140],
                "updated_at": last_ts,
                "mtime": os.path.getmtime(path),
            }
        )
    sessions.sort(key=lambda s: s["mtime"], reverse=True)
    return sessions


def read_transcript(cwd: str, session_id: str, limit: int = 300) -> list[dict]:
    path = _transcript_path(cwd, session_id)
    if not os.path.exists(path):
        return []

    messages = []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line in lines[-limit:]:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = entry.get("type")
        if etype not in ("user", "assistant"):
            continue

        msg = entry.get("message", {})
        content = msg.get("content")
        text_parts = []
        if isinstance(content, str):
            text_parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text":
                    text_parts.append(block.get("text", ""))
                elif btype == "tool_use":
                    args = json.dumps(block.get("input", {}), ensure_ascii=False)[:200]
                    text_parts.append(f"🔧 {block.get('name')}({args})")
                elif btype == "tool_result":
                    result_content = block.get("content")
                    if isinstance(result_content, list):
                        result_content = " ".join(
                            b.get("text", "")
                            for b in result_content
                            if isinstance(b, dict)
                        )
                    text_parts.append(f"📋 {str(result_content)[:400]}")

        text = "\n".join(t for t in text_parts if t)
        if not text:
            continue
        messages.append(
            {"role": etype, "text": text, "timestamp": entry.get("timestamp")}
        )
    return messages


def create_session(cwd: str, prompt: str, name: str | None = None) -> dict:
    session_id = str(uuid.uuid4())
    cmd = [
        CLAUDE_BIN,
        "--bg",
        "--session-id",
        session_id,
        "--permission-mode",
        "bypassPermissions",
    ]
    if name:
        cmd += ["-n", name]
    cmd.append(prompt)

    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "세션 생성 실패"
        )

    return {"session_id": session_id, "output": result.stdout.strip()}


def send_message(cwd: str, session_id: str, prompt: str) -> dict:
    cmd = [
        CLAUDE_BIN,
        "--bg",
        "--resume",
        session_id,
        "--permission-mode",
        "bypassPermissions",
        prompt,
    ]
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip() or result.stdout.strip() or "메시지 전송 실패"
        )

    return {"output": result.stdout.strip()}
