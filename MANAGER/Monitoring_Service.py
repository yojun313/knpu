import time
import requests
from mySQL import mySQL
from datetime import datetime


class Monitoring:
    def __init__(self):
        self.app_key = "a2x6qmtaup9a3upmupiftv2fqfu8sz"
        self.user_keys = ['uvz7oczixno7daxvgxmq65g2gbnsd5', 'uqkbhuy1e1752ryxnjp3hy5g67467m']
        self.z8_status = {"db": True, "crawler": True}  # True는 정상 상태를 의미
        self.omen_status = True  # OMEN 크롤러의 상태

    def main(self):
        while True:
            status = self.check_servers()

            if status is not True:
                error_num, computer, server_type = status
                msg = self.create_error_message(error_num, computer, server_type)

                for key in self.user_keys:
                    self.send_pushover(msg, key)

            print('\n==============================================================')

            time.sleep(1800)  # 30분 대기

    def create_error_message(self, error_num, computer, server_type):
        return (
            f"PROBLEMS DETECTED IN SERVER\n\n"
            f"DateTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Computer: {computer}\n"
            f"Object: {server_type.upper()}\n"
            f"Solution:\n"
            f"1. Check {computer} if it is online\n"
            f"2. Check {computer} network"
        )

    def send_pushover(self, msg, user_key):
        url = 'https://api.pushover.net/1/messages.json'
        message = {
            'token': self.app_key,
            'user': user_key,
            'message': msg
        }

        while True:
            try:
                requests.post(url, data=message)
                return
            except:
                continue

    def check_servers(self):
        print('\n\n==============================================================\n')
        print("DateTime: ", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if not self.check_z8_db():
            return (1, "Z8", "DB Server")

        if not self.check_z8_crawler():
            return (2, "Z8", "Crawler")

        if not self.check_omen_crawler():
            return (3, "OMEN", "Crawler")

        return True

    def check_z8_db(self):
        print("[ Z8 DATABASE SERVER TEST ]")
        mysql_obj = mySQL(host='121.152.225.232', user='admin', password='bigmaclab2022!', port=3306)

        if not mysql_obj.showAllDB():
            print("접속 실패")
            if self.z8_status["db"]:  # 이전에 정상이었다면 (즉, 상태 변화가 있을 때만 알림 전송)
                self.z8_status["db"] = False
                return False
        else:
            if not self.z8_status["db"]:  # 복구되었을 때만 알림
                self.notify_recovery("Z8", "DB Server")
                self.z8_status["db"] = True
            print("접속 정상")
        return True

    def check_z8_crawler(self):
        return self.check_crawler_server("Z8", "http://bigmaclab-crawler.kro.kr:81", "crawler")

    def check_omen_crawler(self):
        return self.check_crawler_server("OMEN", "http://bigmaclab-crawler.kro.kr:80", "crawler")

    def check_crawler_server(self, computer, url, server_type):
        print(f"[ {computer.upper()} {server_type.upper()} SERVER TEST ]")
        try:
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                if computer == "Z8" and not self.z8_status[server_type]:  # 복구될 때만 알림 전송
                    self.notify_recovery(computer, server_type)
                    self.z8_status[server_type] = True
                elif computer == "OMEN" and not self.omen_status:
                    self.notify_recovery(computer, server_type)
                    self.omen_status = True
                print("접속 정상")
            else:
                print("접속 실패")
                if computer == "Z8" and self.z8_status[server_type]:  # 상태가 변할 때만 알림 전송
                    self.z8_status[server_type] = False
                    return False
                elif computer == "OMEN" and self.omen_status:
                    self.omen_status = False
                    return False
        except requests.exceptions.RequestException:
            print("접속 실패")
            if computer == "Z8" and self.z8_status[server_type]:  # 상태가 변할 때만 알림 전송
                self.z8_status[server_type] = False
                return False
            elif computer == "OMEN" and self.omen_status:
                self.omen_status = False
                return False
        return True

    def notify_recovery(self, computer, server_type):
        recovery_msg = (
            f"SERVER RECOVERED\n\n"
            f"DateTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"{computer} {server_type.upper()} server is stable now"
        )
        for key in self.user_keys:
            self.send_pushover(recovery_msg, key)


monitoring_obj = Monitoring()
monitoring_obj.main()
