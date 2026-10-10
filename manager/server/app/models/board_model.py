from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID, uuid4


class AddVersionDto(BaseModel):
    versionName: str
    changeLog: str
    features: str
    details: str
    fullUpdate: bool


class VersionBoardSchema(BaseModel):
    uid: str
    versionName: str
    releaseDate: str
    changeLog: str
    features: str
    status: str
    details: str


class AddBugDto(BaseModel):
    writerUid: str = ""
    versionName: str
    bugTitle: str
    bugText: str
    programLog: str


class BugBoardSchema(BaseModel):
    uid: str
    writerUid: str
    writerName: str
    versionName: str
    bugTitle: str
    bugText: str
    datetime: datetime
    programLog: str


class AddPostDto(BaseModel):
    writerUid: str = ""
    title: str
    text: str
    broadcastNotify: bool = False


class BugReplyDto(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    requestId: UUID = Field(default_factory=uuid4)

    @field_validator("text")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("답변 내용을 입력해주세요.")
        return value


class CommentDto(BaseModel):
    text: str = Field(min_length=1, max_length=10000)
    requestId: UUID = Field(default_factory=uuid4)

    @field_validator("text")
    @classmethod
    def nonempty_text(cls, value: str) -> str:
        return BugReplyDto.nonempty_text(value)


class FreeBoardSchema(BaseModel):
    uid: str
    writerUid: str
    writerName: str
    title: str
    text: str
    datetime: datetime
    viewCnt: list
