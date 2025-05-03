from fastapi import APIRouter, HTTPException
from MANAGER.server.app.models.user_model import UserCreate, UserSchema
from MANAGER.server.app.services import user_service

router = APIRouter()

@router.post("/", response_model=UserSchema)
def create(user: UserCreate):
    return user_service.create_user(user)

@router.delete("/{user_id}")
def delete(user_id: str):
    if not user_service.delete_user(user_id):
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted"}
