"""전역 LLM 모듈(system.llm)을 쓰는 얇은 어댑터.

엔드포인트/모델/폴백 설정은 모두 .env(LLM_*)에 있다.
기존 호출부 계약을 그대로 유지한다: (본문, 모델이름) 튜플을 돌려준다.
"""

from system.llm import chat


def llm_generate(query):
    result = chat(prompt=query)
    return result.text, result.display_model
