"""MCDM 공유 계산 코어 (PolyDecision 0단계).

여러 방법(AHP·BWM·엔트로피·직접평정·SAW·TOPSIS·VIKOR·EDAS)이 공유하는 순수
계산 프리미티브를 한곳에 모은다. DB·WS 의존 없음, 단위 테스트 대상.

경계 규칙: **여러 방법이 쓰거나 쓸 가능성이 있으면 여기(`mcdm/`); 한 방법에만
의미가 있으면 그 방법 플러그인(`app/services/methods/<name>.py`) 안.**

0단계에서는 물리 이동 없이 기존 모듈(`ahp_calc`·`aggregate`·`consistency`)을
그대로 **재수출**만 한다. 방법 코드는 이 패키지에서 당겨 쓰고, 물리적 통합은
1단계+ 정리 작업으로 미룬다.
"""
