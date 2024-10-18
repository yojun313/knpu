import requests


def send_pushOver(msg, user_key, file_path=None):
    app_key_list = ["a22qabchdf25zzkd1vjn12exjytsjx"]

    for app_key in app_key_list:
        try:
            # Pushover API 설정
            url = 'https://api.pushover.net/1/messages.json'
            # 메시지 내용
            message = {
                'token': app_key,
                'user': user_key,
                'message': msg
            }

            # Pushover에 요청을 보냄
            response = requests.post(url, data=message, files = {
                "attachment": ("image.png", open("/Users/yojunsmacbookprp/Documents/GitHub/BIGMACLAB/MANAGER/test.txt", "rb"), "image/png")
            })
            break
        except Exception as e:
            print(f"오류 발생: {e}")
            continue
send_pushOver('테스트', 'uvz7oczixno7daxvgxmq65g2gbnsd5')