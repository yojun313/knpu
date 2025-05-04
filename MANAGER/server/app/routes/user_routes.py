from fastapi import APIRouter
from app.models.user_model import UserCreate
from app.services.user_service import create_user, delete_user, get_all_users

router = APIRouter()

@router.post("/add")
def addUser(user: UserCreate):
    return create_user(user)

@router.get("")
def loadUsers():
    return get_all_users()

@router.delete("/{userUid}")
def deleteUser(userUid: str):
    return delete_user(userUid)
