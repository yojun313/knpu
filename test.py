import requests

token = "***REMOVED***"  # Replace with your actual token

res= requests.post("https://manager.knpu.re.kr/api/users/admin/pushover", json={"message": "전송 테스트"}, headers={
        "Authorization": f"Bearer {token}"
    })
print(res.status_code)