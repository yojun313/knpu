import glob
import json
import os
import time
from datetime import datetime, timedelta, timezone

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
HOME_DIR = os.path.expanduser("~")

_CACHE_TTL = 30  # seconds — 매 폴링마다 디스크를 다시 훑지 않도록 짧게 캐시
_cache = {"data": None, "at": 0.0}


def _empty_bucket() -> dict:
    return {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0, "messages": 0}


def _add(bucket: dict, usage: dict) -> None:
    bucket["input"] += usage.get("input_tokens", 0) or 0
    bucket["output"] += usage.get("output_tokens", 0) or 0
    bucket["cache_write"] += usage.get("cache_creation_input_tokens", 0) or 0
    bucket["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
    bucket["messages"] += 1


def _total(bucket: dict) -> int:
    return (
        bucket["input"]
        + bucket["output"]
        + bucket["cache_write"]
        + bucket["cache_read"]
    )


def _project_label(cwd: str | None) -> str:
    if not cwd:
        return "(알 수 없음)"
    rel = cwd
    if rel.startswith(HOME_DIR):
        rel = rel[len(HOME_DIR) :].lstrip("/")
    if not rel:
        return "~ (홈 디렉토리)"
    parts = rel.split("/")
    return "/".join(parts[:2]) if len(parts) > 1 else parts[0]


def _extract_preview(entry: dict) -> str:
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return (block.get("text") or "").strip()
    return ""


def compute_usage(force: bool = False) -> dict:
    now = time.time()
    if not force and _cache["data"] is not None and now - _cache["at"] < _CACHE_TTL:
        return _cache["data"]

    totals = _empty_bucket()
    by_model: dict[str, dict] = {}
    by_day: dict[str, dict] = {}
    by_project: dict[str, dict] = {}
    session_rows = []

    now_dt = datetime.now(timezone.utc)
    today_str = now_dt.strftime("%Y-%m-%d")
    active_cutoff = now_dt - timedelta(minutes=5)

    files = sorted(glob.glob(os.path.join(PROJECTS_DIR, "*", "*.jsonl")))

    for path in files:
        session_id = os.path.splitext(os.path.basename(path))[0]
        sess_bucket = _empty_bucket()
        sess_project_counts: dict[str, int] = {}
        model_seen: set[str] = set()
        first_ts = None
        last_ts = None
        preview = ""

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    etype = entry.get("type")

                    if etype == "user" and not preview:
                        preview = _extract_preview(entry)

                    if etype != "assistant":
                        continue

                    msg = entry.get("message", {})
                    usage = msg.get("usage")
                    if not usage:
                        continue

                    model = msg.get("model") or "unknown"
                    ts = entry.get("timestamp")
                    cwd = entry.get("cwd")

                    _add(totals, usage)
                    _add(sess_bucket, usage)
                    model_seen.add(model)

                    bm = by_model.setdefault(model, _empty_bucket())
                    _add(bm, usage)

                    if ts:
                        day = ts[:10]
                        bd = by_day.setdefault(day, _empty_bucket())
                        _add(bd, usage)
                        if first_ts is None or ts < first_ts:
                            first_ts = ts
                        if last_ts is None or ts > last_ts:
                            last_ts = ts

                    if cwd:
                        label = _project_label(cwd)
                        bp = by_project.setdefault(label, _empty_bucket())
                        _add(bp, usage)
                        sess_project_counts[label] = (
                            sess_project_counts.get(label, 0) + 1
                        )
        except FileNotFoundError:
            continue

        if sess_bucket["messages"] == 0:
            continue

        main_project = (
            max(sess_project_counts.items(), key=lambda kv: kv[1])[0]
            if sess_project_counts
            else "(알 수 없음)"
        )
        real_models = [m for m in model_seen if m != "<synthetic>"]
        display_model = (
            sorted(real_models)[0]
            if real_models
            else (sorted(model_seen)[0] if model_seen else "unknown")
        )

        is_active = False
        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
                is_active = last_dt > active_cutoff
            except ValueError:
                pass

        session_rows.append(
            {
                "session_id": session_id,
                "project": main_project,
                "model": display_model,
                "messages": sess_bucket["messages"],
                "total_tokens": _total(sess_bucket),
                "input": sess_bucket["input"],
                "output": sess_bucket["output"],
                "cache_write": sess_bucket["cache_write"],
                "cache_read": sess_bucket["cache_read"],
                "first_ts": first_ts,
                "last_ts": last_ts,
                "preview": preview[:160],
                "active": is_active,
            }
        )

    session_rows.sort(key=lambda s: s["last_ts"] or "", reverse=True)

    today_bucket = by_day.get(today_str, _empty_bucket())

    daily = [
        {"date": d, "total": _total(b), **b} for d, b in sorted(by_day.items())[-30:]
    ]

    model_rows = sorted(
        ({"model": m, "total": _total(b), **b} for m, b in by_model.items()),
        key=lambda r: r["total"],
        reverse=True,
    )

    project_rows_all = sorted(
        ({"project": p, "total": _total(b), **b} for p, b in by_project.items()),
        key=lambda r: r["total"],
        reverse=True,
    )
    TOP_N = 12
    project_rows = project_rows_all[:TOP_N]
    if len(project_rows_all) > TOP_N:
        rest = project_rows_all[TOP_N:]
        etc = _empty_bucket()
        for r in rest:
            etc["input"] += r["input"]
            etc["output"] += r["output"]
            etc["cache_write"] += r["cache_write"]
            etc["cache_read"] += r["cache_read"]
            etc["messages"] += r["messages"]
        project_rows.append(
            {"project": f"기타 ({len(rest)}개 디렉토리)", "total": _total(etc), **etc}
        )

    last_activity = max(
        (r["last_ts"] for r in session_rows if r["last_ts"]), default=None
    )

    data = {
        "generated_at": now_dt.isoformat(),
        "totals": {
            **totals,
            "total": _total(totals),
            "sessions": len(session_rows),
            "days_active": len(by_day),
        },
        "today": {**today_bucket, "total": _total(today_bucket)},
        "active_sessions": sum(1 for r in session_rows if r["active"]),
        "last_activity": last_activity,
        "by_model": model_rows,
        "daily": daily,
        "by_project": project_rows,
        "recent_sessions": session_rows[:20],
        "source_dir": PROJECTS_DIR,
    }

    _cache["data"] = data
    _cache["at"] = now
    return data
