import requests

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI4ZTY5MTA4ZC00MjBiLTRmZGEtYTQ5NS00MzJmMWQzN2E2ZDAiLCJuYW1lIjoiYWRtaW4iLCJkZXZpY2UiOiJZb2p1bnMtTWFjQm9vay1Qcm8ubG9jYWwifQ.BwYxe68KH9Un5AP5GBK675Z7vLVjVgkUfy9ysGO5qN0"  # Replace with your actual token

res= requests.post("https://manager.knpu.re.kr/api/users/admin/pushover", json={"message": "전송 테스트"}, headers={
        "Authorization": f"Bearer {token}"
    })
print(res.status_code)