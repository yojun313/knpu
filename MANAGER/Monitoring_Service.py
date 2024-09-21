import time
import requests
from mySQL import mySQL
from datetime import datetime

class monitoring:
    def __init__(self):
        self.app_key = "a2x6qmtaup9a3upmupiftv2fqfu8sz"
        self.user_key = ['uvz7oczixno7daxvgxmq65g2gbnsd5', 'uqkbhuy1e1752ryxnjp3hy5g67467m']

    def main(self):
        while True:
            status = self.check_servers()  # 작업 실행
            msg = (
                "PROBLEMS DETECTED IN SERVER\n"
                f"\nDateTime: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n"
            )

            if status == True:
                pass
            else:
                error_num = status[1]
                if error_num == 1:
                    msg += (
                        "Computer: Z8\n"
                        "Object: DB Server\n"
                        "Solution:\n"
                        "1. Check Z8 if it is online\n"
                        "2. Check Z8 network"
                    )
                elif error_num == 2:
                    msg += (
                        "Computer: Z8\n"
                        "Object: CRAWLER\n"
                        "Solution:\n"
                        "1. Check Z8 if it is online\n"
                        "2. Check Z8 network"
                    )

                elif error_num == 3:
                    msg += (
                        "Computer: OMEN\n"
                        "Object: CRAWLER\n"
                        "Solution:\n"
                        "1. Check OMEN if it is online\n"
                        "2. Check OMEN network"
                    )
                for key in self.user_key:
                    self.send_pushOver(msg, key)
                return

            time.sleep(1800)  # 1시간(3600초) 대기

    def send_pushOver(self, msg, user_key):
        while True:
            try:
                # Pushover API 설정
                url = 'https://api.pushover.net/1/messages.json'
                # 메시지 내용
                message = {
                    'token': self.app_key,
                    'user': user_key,
                    'message': msg
                }
                # Pushover에 요청을 보냄
                response = requests.post(url, data=message)
                return
            except:
                continue

    def check_servers(self):
        status = True
        # Z8 DB
        print('\n\n==============================================================')
        print("DateTime: ", end='')
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print()

        print("[ Z8 DATABASE SERVER TEST ]")
        mysql_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306)
        if mysql_obj.showAllDB() == []:
            print("접속 실패")
            status = (False, 1)
        else:
            print("접속 정상")
        print('--------------------------------------------------------------')

        # Z8 CRAWLER
        print("[ Z8 CRAWLER SERVER TEST ]")
        url = 'http://bigmaclab-crawler.kro.kr:81'
        try:
            response = requests.get(url, timeout=10)
            # 상태 코드가 200번대면 성공
            if response.status_code == 200:
                print("접속 정상")
            else:
                print("접속 정상")
                status = (False, 2)

        except requests.exceptions.RequestException as e:
            # 요청이 실패했을 때의 예외 처리
            print("접속 실패")
            status = (False, 2)
        print('--------------------------------------------------------------')

        # Z8 CRAWLER
        print("[ OMEN CRAWLER SERVER TEST ]")
        url = 'http://bigmaclab-crawler.kro.kr:80'
        try:
            response = requests.get(url, timeout=10)
            # 상태 코드가 200번대면 성공
            if response.status_code == 200:
                print("접속 정상")
            else:
                print("접속 실패")
                status = (False, 3)

        except requests.exceptions.RequestException as e:
            # 요청이 실패했을 때의 예외 처리
            print("접속 실패")
            status = (False, 3)
        print('\n==============================================================')

        return status



monitoring_obj = monitoring()
monitoring_obj.main()