#
import requests
def sendPushOver(msg, user_keys = [], image_path=False):
    app_key_list = ["a22qabchdf25zzkd1vjn12exjytsjx"]
    for app_key in app_key_list:
        for user_key in user_keys:
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
                if image_path == False:
                    response = requests.post(url, data=message)
                else:
                    response = requests.post(url, data=message, files={
                        "attachment": (
                            "image.png", open(image_path, "rb"),
                            "image/png")
                    })
            except:
                continue
