from pydantic import BaseModel
from typing import List, Optional


class Member(BaseModel):
    uid: Optional[str] = None
    name: str
    position: str
    affiliation: str
    section: str
    email: str
    학력: List[str] = []
    경력: List[str] = []
    연구: List[str] = []
    image: Optional[str] = ""


class News(BaseModel):
    uid: Optional[str] = None
    image: str
    title: str
    content: str
    date: str
    url: str


class Paper(BaseModel):
    uid: Optional[str] = None
    title: str
    authors: List[str]
    conference: str
    link: str


class PaperRequest(BaseModel):
    year: int
    paper: Paper


class GroupPhoto(BaseModel):
    uid: Optional[str] = None
    url: str
    caption: str
    date: Optional[str] = None
