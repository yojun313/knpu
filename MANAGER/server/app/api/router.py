from fastapi import APIRouter, HTTPException
from app.api.users.models import UserCreate, UserSchema
from app.api.users import service

router = APIRouter()

@router.post("/", response_model=UserSchema)
def create(user: UserCreate):
    return service.create_user(user)

@router.delete("/{user_id}")
def delete(user_id: str):
    if not service.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}
