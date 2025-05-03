
from bson import ObjectId
from db import user_collection
from models.user_model import UserCreate
import uuid

def create_user(user: UserCreate):
    user_dict = user.model_dump()
    print(user_dict)
    # result = user_collection.insert_one(user_dict)
    # user_dict["_id"] = str(result.inserted_id)
    return user_dict

def get_user(user_id: str):
    user = user_collection.find_one({"_id": ObjectId(user_id)})
    if user:
        user["_id"] = str(user["_id"])
    return user

def get_all_users():
    return [ {**u, "_id": str(u["_id"])} for u in user_collection.find() ]

def delete_user(user_id: str):
    result = user_collection.delete_one({"_id": ObjectId(user_id)})
    return result.deleted_count > 0
