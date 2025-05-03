from fastapi import APIRouter
from app.models.user_model import UserCreate
from app.services.user_service import create_user, delete_user, get_all_users

router = APIRouter()

@router.post("/add")
def create_user(user: UserCreate):
    return create_user(user)

@router.get("")
def load_users():
    return get_all_users()

@router.delete("/{userUid}")
def delete_user(userUid: str):
    return delete_user(userUid)
