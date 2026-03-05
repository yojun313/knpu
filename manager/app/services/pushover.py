import requests
from config import ADMIN_PUSHOVERKEY
from services.api import Request

def sendPushOver(msg):
    Request('post', '/users/admin/pushover', json={"message": msg})
    
