import os
VERSION = '2.7.8'

'''
    0: local
    1: production
'''

ASSETS_PATH = os.path.join(os.path.dirname(__file__), "assets")
ADMIN_PUSHOVERKEY = '***REMOVED***'
ADMIN_PASSWORD = "***REMOVED***"

mode = 1

if mode == 0:
    MANAGER_SERVER_API = "http://localhost:8000/api"
    MANAGER_PROGRESS_API = "http://localhost:8080"
else:
    MANAGER_SERVER_API = "https://manager.knpu.re.kr/api"
    MANAGER_PROGRESS_API = "https://manager-progress.knpu.re.kr"
