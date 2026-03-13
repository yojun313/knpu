from services.api import Request

def sendAdminPushOver(msg):
    Request('post', '/users/admin/pushover', json={"message": msg})
    
