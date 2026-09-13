from pydantic import BaseModel


class StatisticsOption(BaseModel):
    pid: str
    category: str
    platform: str
    # 워드클라우드 분석 전용 옵션 (다른 분석에서는 무시됨)
    wc_period: str = "total"  # total | 1d | 1w | 1m | 3m | 6m | 1y
    wc_max_words: int = 100
    wc_exclude: list[str] = []
