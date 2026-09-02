"""인구통계(demographics) 스키마·응답의 단일 출처.

- **스키마**는 `surveys.demographics`에 산다: 항목마다 라벨/유형/필수/보기(코드).
- **응답**은 `respondents.attributes`에 산다: `{field_id: value}` (코드 기반).

설계 화면(survey_routes), 응답 수집(respond_routes·entry_routes), 반입 양식·내보내기
(export_routes·sheet_export), 인쇄(print/docx), 결과 필터(result_routes)가 전부 이 파일의
함수만 통해 스키마를 해석한다 — csv_schema, ahp_calc.to_stored_pair와 같은 "한 곳에만" 원칙.
"""

from __future__ import annotations

import uuid

TYPES = ("single", "multi", "number", "text")
CHOICE_TYPES = ("single", "multi")

# 복수선택 저장/직렬화 구분자. 코드 안에 이 문자가 없다고 가정한다(normalize에서 제거).
MULTI_SEP = ";"


def _clean_str(v) -> str:
    return str(v if v is not None else "").strip()


def normalize_demographics(raw) -> list[dict]:
    """설계 패널이 보낸 항목 배열을 저장 가능한 형태로 정규화한다.

    - id: 있으면 유지, 없으면 새로 부여(응답이 이 id로 저장되므로 안정적이어야 한다)
    - type: 화이트리스트 밖이면 'text'
    - 선택형: 보기 라벨/코드 trim, 빈 항목·중복 코드 제거. 코드 없으면 1,2,3… 자동 부여
    - required: bool, order: 재부여
    """
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    seen_ids: set[str] = set()
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        label = _clean_str(item.get("label"))
        if not label:
            continue
        ftype = item.get("type")
        if ftype not in TYPES:
            ftype = "text"
        fid = _clean_str(item.get("id")) or uuid.uuid4().hex[:8]
        if fid in seen_ids:
            fid = uuid.uuid4().hex[:8]
        seen_ids.add(fid)

        field = {
            "id": fid,
            "label": label,
            "type": ftype,
            "required": bool(item.get("required")),
            "order": i,
        }
        if ftype in CHOICE_TYPES:
            options: list[dict] = []
            seen_codes: set[str] = set()
            for j, opt in enumerate(item.get("options") or []):
                if isinstance(opt, dict):
                    olabel = _clean_str(opt.get("label"))
                    ocode = _clean_str(opt.get("code")).replace(MULTI_SEP, "")
                else:
                    olabel = _clean_str(opt)
                    ocode = ""
                if not olabel:
                    continue
                if not ocode:
                    ocode = str(j + 1)
                if ocode in seen_codes:
                    continue
                seen_codes.add(ocode)
                options.append({"code": ocode, "label": olabel})
            field["options"] = options
        out.append(field)
    return out


def _option_by(field: dict, key: str, value: str) -> dict | None:
    for o in field.get("options", []):
        if o.get(key) == value:
            return o
    return None


def coerce_answer(field: dict, raw) -> tuple[object, str | None]:
    """한 항목의 입력값을 저장형(코드/숫자/문자열)으로 변환한다. (값, 오류메시지|None).

    빈 값은 (None, None) — 필수 검사는 validate_required가 따로 한다.
    선택형은 코드도 라벨도 받는다(종이 전사·엑셀 반입 편의).
    """
    ftype = field.get("type")
    label = field.get("label", "")

    if ftype == "multi":
        parts: list[str] = []
        if isinstance(raw, (list, tuple)):
            parts = [_clean_str(x) for x in raw]
        else:
            parts = [p.strip() for p in _clean_str(raw).split(MULTI_SEP)]
        parts = [p for p in parts if p]
        if not parts:
            return None, None
        codes: list[str] = []
        for p in parts:
            opt = _option_by(field, "code", p) or _option_by(field, "label", p)
            if not opt:
                return None, f"'{label}'에 없는 보기: {p}"
            if opt["code"] not in codes:
                codes.append(opt["code"])
        return codes, None

    if ftype == "single":
        s = _clean_str(raw)
        if not s:
            return None, None
        opt = _option_by(field, "code", s) or _option_by(field, "label", s)
        if not opt:
            return None, f"'{label}'에 없는 보기: {s}"
        return opt["code"], None

    if ftype == "number":
        s = _clean_str(raw)
        if not s:
            return None, None
        try:
            n = float(s)
        except ValueError:
            return None, f"'{label}'은(는) 숫자여야 합니다: {s}"
        return int(n) if n == int(n) else n, None

    # text
    s = _clean_str(raw)
    return (s or None), None


def coerce_attributes(demographics: list[dict], answers: dict) -> tuple[dict, list[str]]:
    """{field_id: raw} → ({field_id: stored}, errors[]). 빈 값은 결과에서 제외."""
    by_id = {f["id"]: f for f in demographics}
    out: dict = {}
    errors: list[str] = []
    for fid, raw in (answers or {}).items():
        field = by_id.get(fid)
        if not field:
            continue
        value, err = coerce_answer(field, raw)
        if err:
            errors.append(err)
        elif value is not None and value != [] and value != "":
            out[fid] = value
    return out, errors


def validate_required(demographics: list[dict], attributes: dict) -> list[str]:
    missing = []
    for f in demographics:
        if not f.get("required"):
            continue
        v = (attributes or {}).get(f["id"])
        if v is None or v == "" or v == []:
            missing.append(f["label"])
    return missing


def column_label(field: dict) -> str:
    """반입 양식 헤더. 선택형은 코드 힌트를, 복수선택은 구분자 안내를 괄호로 덧붙인다."""
    base = field["label"]
    if field.get("type") in CHOICE_TYPES and field.get("options"):
        hint = ", ".join(f"{o['code']}={o['label']}" for o in field["options"])
        if field["type"] == "multi":
            return f"{base} ({hint}; 여러 개는 {MULTI_SEP} 로 구분)"
        return f"{base} ({hint})"
    return base


def column_labels(demographics: list[dict]) -> list[str]:
    return [column_label(f) for f in demographics]


def resolve_for_export(field: dict, stored) -> dict:
    """저장형 → {code, label}. 복수선택은 code/label 모두 MULTI_SEP 결합."""
    ftype = field.get("type")
    if stored is None:
        return {"code": "", "label": ""}
    if ftype == "multi":
        codes = stored if isinstance(stored, (list, tuple)) else [stored]
        labels = []
        for c in codes:
            o = _option_by(field, "code", str(c))
            labels.append(o["label"] if o else str(c))
        return {"code": MULTI_SEP.join(str(c) for c in codes), "label": MULTI_SEP.join(labels)}
    if ftype == "single":
        o = _option_by(field, "code", str(stored))
        return {"code": str(stored), "label": o["label"] if o else str(stored)}
    # number / text
    return {"code": str(stored), "label": str(stored)}
