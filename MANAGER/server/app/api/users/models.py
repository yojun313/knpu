from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId

class UserBase(BaseModel):
    name: str
    email: str

class UserCreate(UserBase):
    pass

class UserDB(UserBase):
    id: Optional[str] = Field(alias="_id")

    class Config:
        orm_mode = True
        json_encoders = {
            ObjectId: str
        }
