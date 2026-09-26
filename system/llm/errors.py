class LLMError(RuntimeError):
    """LLM 호출이 최종적으로 실패했을 때 발생한다.

    폴백까지 모두 실패한 경우에만 올라오므로, 호출부는 이 예외 하나만
    잡으면 된다. attempts에는 시도별 (라벨, 예외) 이력이 담긴다.
    """

    def __init__(self, message: str, attempts: list[tuple[str, Exception]] | None = None):
        self.attempts = attempts or []
        if self.attempts:
            detail = "; ".join(f"{label}: {exc}" for label, exc in self.attempts)
            message = f"{message} ({detail})"
        super().__init__(message)
