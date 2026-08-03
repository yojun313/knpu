from pydantic import BaseModel


class StatisticsOption(BaseModel):
    pid: str
    category: str
    platform: str
