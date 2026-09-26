"""전역 LLM 모듈(system.llm)을 쓰는 얇은 어댑터.

엔드포인트/모델/폴백 설정은 모두 .env(LLM_*)에 있다.
기존 계약 유지: 성공 시 문자열, 실패 시 (0, 오류문자열) 튜플.
"""

import traceback

from system.llm import LLMError, complete


def generateLLM(query):
    try:
        return complete(query)
    except LLMError:
        return (0, traceback.format_exc())
