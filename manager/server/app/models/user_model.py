from pydantic import BaseModel, Field
from typing import Optional

class UserSchema(BaseModel):
    id: Optional[str] = Field(alias="_id")
    uid: str
    name: str
    email: str
    pushoverKey: Optional[str] = None
    device_list: Optional[list[str]] = None

class UserCreate(BaseModel):
    name: str
    email: str
    pushoverKey: Optional[str] = None