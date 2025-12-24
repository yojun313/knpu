from pydantic import BaseModel
from typing import Optional

class KemKimOption(BaseModel):
    pid: str
    tokenfile_name: str
    startdate: str
    enddate: str
    period: str
    topword: int
    weight: float
    graph_wordcnt: int
    split_option: str
    split_custom: Optional[str] = None
    filter_option: bool
    trace_standard: str
    ani_option: bool
    exception_word_list: list
    exception_filename: str
    
class TokenizeOption(BaseModel):
    pid: str
    column_names: list

class HateOption(BaseModel):
    pid: str
    option_num: int