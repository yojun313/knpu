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
    수상: List[str] = []
    연구: List[str] = []
    image: Optional[str] = ""


class News(BaseModel):
    uid: Optional[str] = None
    image: Optional[str] = None
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
    uid: Optional[str] = None
    title: str
    authors: List[str] = []
    authors_kr: Optional[List[Optional[str]]] = None
    year: int
    published_date: Optional[str] = None
    publication_type: Optional[str] = None
    journal_type: Optional[str] = None
    venue: Optional[str] = ""
    volume: Optional[str] = None
    issue: Optional[str] = None
    pages: Optional[str] = None
    publisher: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = ""
    abstract: Optional[str] = None
    language: Optional[str] = None
    apa_citation: Optional[str] = None
    keywords: Optional[List[str]] = None
    source_api: Optional[str] = None
    api_confidence: Optional[float] = None
    fetched_at: Optional[str] = None
    verified: Optional[bool] = False
    notes: Optional[str] = ""


class GalleryPost(BaseModel):
    uid: Optional[str] = None
    title: str
    content: str = ""
    date: Optional[str] = None
    photos: List[str] = []
    schema_version: int = 2


class FaqCategory(BaseModel):
    uid: Optional[str] = None
    name: str                   # 그룹 제목 (예: "01 · 지원 · 선발")
    order: int = 0              # 카테고리(그룹) 표시 순서 (오름차순)


class FaqItem(BaseModel):
    uid: Optional[str] = None
    category: str = ""          # FaqCategory.name 과 매칭되는 그룹 제목
    question: str               # 앞의 "Q1." 번호는 렌더링 시 자동으로 붙는다
    answer: str = ""            # 평문. 줄바꿈은 렌더링 시 <br>로 변환된다
    order: int = 0              # 같은 카테고리 안에서의 정렬 순서 (오름차순)


class Popup(BaseModel):
    uid: Optional[str] = None
    title: str
    content: str
    image: Optional[str] = ""
    link_url: Optional[str] = ""
    start_date: str
    end_date: str
    is_active: bool = True
    created_at: Optional[str] = None


class SignupRequest(BaseModel):
    username: str
    name: str
    email: str
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendCodeRequest(BaseModel):
    username: str


class LoginRequest(BaseModel):
    username: str
    password: str


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    username: str
    code: str
    new_password: str


class UpdateRoleRequest(BaseModel):
    role: str


class PasskeyRegisterVerifyRequest(BaseModel):
    credential: dict
    device_name: Optional[str] = None


class PasskeyLoginVerifyRequest(BaseModel):
    credential: dict


class PasskeyClientErrorRequest(BaseModel):
    context: str
    name: Optional[str] = None
    message: Optional[str] = None
