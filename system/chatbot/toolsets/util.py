"""계산·날짜 같은 작은 도구 (모델이 암산·날짜 계산을 틀리지 않게)."""

import ast
import math
import operator
from datetime import date, datetime, timedelta

from ..registry import tool

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}
_FUNCS = {
    "sqrt": math.sqrt, "log": math.log, "log10": math.log10, "exp": math.exp,
    "abs": abs, "round": round, "min": min, "max": max, "sum": lambda *a: sum(a),
    "mean": lambda *a: sum(a) / len(a),
}  # fmt: skip


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and (abs(left) > 1e6 or abs(right) > 64):
            raise ValueError("지수가 너무 큽니다.")
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _FUNCS
        and not node.keywords
    ):
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    if isinstance(node, ast.Name) and node.id in ("pi", "e"):
        return getattr(math, node.id)
    raise ValueError(
        "숫자와 + - * / // % ** ( ), sqrt·log·exp·abs·round·min·max·sum·mean 만 쓸 수 있습니다."
    )


@tool(
    "calc",
    "사칙연산·비율·평균 계산(암산하지 말고 이 도구를 쓴다). 예: (128-97)/97*100",
    {"expression": "계산식"},
    label="계산 · {expression}",
)
def calc(ctx, expression=""):
    expr = (
        str(expression)
        .replace("×", "*")
        .replace("÷", "/")
        .replace("^", "**")
        .replace(",", "")
    )
    if not expr.strip() or len(expr) > 300:
        raise ValueError("계산식을 300자 이하로 입력해 주시기 바랍니다.")
    try:
        value = _eval(ast.parse(expr, mode="eval").body)
    except (SyntaxError, ZeroDivisionError, OverflowError, TypeError) as e:
        raise ValueError(f"계산할 수 없는 식입니다: {e}") from e
    return {
        "expression": expr.strip(),
        "value": round(value, 10) if isinstance(value, float) else value,
    }


@tool(
    "date_calc",
    "오늘 날짜·요일, 두 날짜 사이 일수, 며칠 뒤/앞 날짜 계산",
    {
        "start": "(선택) 기준 날짜 YYYY-MM-DD(비우면 오늘)",
        "end": "(선택) 비교할 날짜 YYYY-MM-DD",
        "days": "(선택) 더할 일수(음수면 이전)",
    },
    label="날짜 계산",
)
def date_calc(ctx, start="", end="", days=""):
    week = "월화수목금토일"

    def parse(v):
        try:
            return datetime.strptime(
                str(v).strip().replace("/", "-").replace(".", "-"), "%Y-%m-%d"
            ).date()
        except ValueError:
            raise ValueError(
                "날짜는 YYYY-MM-DD 형식으로 입력해 주시기 바랍니다."
            ) from None

    base = parse(start) if str(start).strip() else date.today()
    out = {
        "today": date.today().isoformat(),
        "start": base.isoformat(),
        "start_weekday": week[base.weekday()] + "요일",
    }
    if str(end).strip():
        e = parse(end)
        out.update(
            end=e.isoformat(),
            end_weekday=week[e.weekday()] + "요일",
            days_between=(e - base).days,
        )
    if str(days).strip():
        try:
            d = base + timedelta(days=int(float(days)))
        except (ValueError, OverflowError):
            raise ValueError("days 는 정수로 입력해 주시기 바랍니다.") from None
        out.update(result=d.isoformat(), result_weekday=week[d.weekday()] + "요일")
    return out
