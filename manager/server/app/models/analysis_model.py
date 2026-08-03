from pydantic import BaseModel


class TokenizeOption(BaseModel):
    pid: str
    column_names: list


class HateOption(BaseModel):
    pid: str
    option_num: int
