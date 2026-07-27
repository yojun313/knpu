import json
import os
import time
import urllib.error
import urllib.request

# Claude Code CLI가 세션(5시간)/주간(7일) 사용량 한도를 표시할 때 실제로 호출하는
# 비공식 내부 엔드포인트다 (claude 바이너리 문자열 분석으로 확인). 공식 문서화된 API가
# 아니므로 CLI 업데이트에 따라 언제든 바뀌거나 사라질 수 있다 — 실패 시 조용히 에러를
# 반환하고 나머지 사용량 통계(토큰 집계)에는 영향이 없게 한다.
CREDENTIALS_PATH = os.path.expanduser("~/.claude/.credentials.json")
USAGE_ENDPOINT = "https://api.anthropic.com/api/oauth/usage"

_CACHE_TTL = 60  # seconds — 개인 계정 토큰으로 호출하는 외부 요청이라 과도하게 자주 부르지 않는다
_cache = {"data": None, "at": 0.0}


def _read_token() -> str | None:
    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            creds = json.load(f)
        return creds.get("claudeAiOauth", {}).get("accessToken")
    except Exception:
        return None


def _read_subscription_type() -> str | None:
    try:
        with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            creds = json.load(f)
        return creds.get("claudeAiOauth", {}).get("subscriptionType")
    except Exception:
        return None


def get_account_usage(force: bool = False) -> dict:
    now = time.time()
    if not force and _cache["data"] is not None and now - _cache["at"] < _CACHE_TTL:
        return _cache["data"]

    token = _read_token()
    if not token:
        return {"error": "~/.claude/.credentials.json에서 인증 토큰을 읽을 수 없습니다"}

    req = urllib.request.Request(
        USAGE_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        result = {
            "error": f"사용량 조회 실패 (HTTP {e.code}) — 로컬 CLI 로그인이 만료되었을 수 있습니다"
        }
        _cache["data"] = result
        _cache["at"] = now
        return result
    except Exception as e:
        result = {"error": f"사용량 조회 실패: {e}"}
        _cache["data"] = result
        _cache["at"] = now
        return result

    limits_by_kind = {limit.get("kind"): limit for limit in (raw.get("limits") or [])}
    session_limit = limits_by_kind.get("session") or {}
    weekly_limit = limits_by_kind.get("weekly_all") or {}

    five_hour = raw.get("five_hour") or {}
    seven_day = raw.get("seven_day") or {}

    result = {
        "subscription_type": _read_subscription_type(),
        "session": {
            "percent_used": session_limit.get("percent", five_hour.get("utilization")),
            "resets_at": session_limit.get("resets_at") or five_hour.get("resets_at"),
            "severity": session_limit.get("severity"),
            "is_active": session_limit.get("is_active"),
        },
        "weekly": {
            "percent_used": weekly_limit.get("percent", seven_day.get("utilization")),
            "resets_at": weekly_limit.get("resets_at") or seven_day.get("resets_at"),
            "severity": weekly_limit.get("severity"),
            "is_active": weekly_limit.get("is_active"),
        },
        "extra_usage_enabled": (raw.get("extra_usage") or {}).get("is_enabled", False),
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
    }

    _cache["data"] = result
    _cache["at"] = now
    return result
