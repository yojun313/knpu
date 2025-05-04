from pydantic import BaseModel
from datetime import datetime

class AddVersionDto(BaseModel):
    versionName: str
    changeLog: str
    features: str
    status: str
    details: str
    sendPushOver: bool

class VersionBoardSchema(BaseModel):
    uid: str
    versionName: str
    releaseDate: str
    changeLog: str
    features: str
    status: str
    details: str

class AddBugDto(BaseModel):
    writerUid: str
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
    writerUid: str
    title: str
    text: str
    sendPushOver: bool

class FreeBoardSchema(BaseModel):
    uid: str
    writerUid: str
    writerName: str
    title: str
    text: str
    datetime: datetime
    viewCnt: int
    