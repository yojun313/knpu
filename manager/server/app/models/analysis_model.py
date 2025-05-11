from pydantic import BaseModel

class KemKimOption(BaseModel):
    tokenfile_name: str
    startdate: str
    enddate: str
    period: str
    topword: int
    weight: float
    graph_wordcnt: int
    split_option: str
    split_custom: str
    filter_option: bool
    trace_starndard: str
    ani_option: bool
    exception_word_list: list
    exception_filename: str
    